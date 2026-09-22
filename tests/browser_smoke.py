"""Browser checks with synthetic audio and a mocked provider response: no API credits used.

Run with a started container, playwright installed, and Chromium available:
  python tests/browser_smoke.py
Optional: CHROMIUM_EXECUTABLE=/path/to/chromium and APP_URL=http://127.0.0.1:8765
"""
import io
import json
import os
import wave
from pathlib import Path
from urllib.parse import unquote

from playwright.sync_api import sync_playwright, expect

OUTPUT = Path("test-results")
OUTPUT.mkdir(exist_ok=True)
URL = os.environ.get("APP_URL", "http://127.0.0.1:8765")
RESULT = {
    "metadata": {"duration": 3.0, "channels": 1, "request_id": "synthetic-test"},
    "results": {
        "channels": [{"alternatives": [{"transcript": "Olá, Deepgram! Vamos revisar o atendimento.", "confidence": 0.98}]}],
        "utterances": [
            {"start": 0, "speaker": 0, "channel": 0, "transcript": "Olá, Deepgram!"},
            {"start": 1.5, "speaker": 1, "channel": 0, "transcript": "Vamos revisar o atendimento."},
        ],
    },
}
audio = io.BytesIO()
with wave.open(audio, "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(8000)
    wav.writeframes(b"\0\0" * 24000)

with sync_playwright() as playwright:
    launch = {"headless": True}
    if os.environ.get("CHROMIUM_EXECUTABLE"):
        launch["executable_path"] = os.environ["CHROMIUM_EXECUTABLE"]
    browser = playwright.chromium.launch(**launch)
    context = browser.new_context(viewport={"width": 1440, "height": 1050}, accept_downloads=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    balance_state = {"amount": "194.125", "error": None, "calls": 0}
    def balance(route):
        balance_state["calls"] += 1
        if balance_state["error"]:
            route.fulfill(status=502, json={"error": balance_state["error"]})
        else:
            route.fulfill(json={"balances": [{"amount": balance_state["amount"], "units": "USD"}], "checked_at": "2026-09-21T15:00:00+00:00"})
    page.route("**/api/balance", balance)
    page.goto(URL)
    expect(page.locator("#connection")).not_to_have_text("Verificando configuração…")
    actual = page.request.get(URL + "/api/config").json()
    if not actual["configured"]:
        expect(page.locator("#setup")).to_be_visible()
        expect(page.locator("#submit")).to_be_disabled()
    page.screenshot(path=str(OUTPUT / "desktop-setup.png"), full_page=True)

    def configured(route):
        response = route.fetch()
        data = response.json()
        data["configured"] = True
        route.fulfill(response=response, json=data)

    calls = []
    def transcribe(route):
        # The browser must send the file as the raw body, never wrapped in multipart:
        # a multipart wrapper would mean the whole upload is buffered again.
        calls.append({"body": route.request.post_data_buffer, "headers": route.request.headers})
        route.fulfill(json={"result": RESULT})

    page.route("**/api/config", configured)
    page.route("**/api/transcribe", transcribe)
    page.reload()
    expect(page.locator("#connection")).to_have_text("Chave configurada")
    expect(page.locator("#balance-value")).to_contain_text("194,125")
    balance_state["amount"] = "190.25"
    page.locator("#refresh-balance").click()
    expect(page.locator("#balance-value")).to_contain_text("190,25")
    page.locator("#file").set_input_files({"name": "reunião.wav", "mimeType": "audio/wav", "buffer": audio.getvalue()})
    expect(page.locator("#submit")).to_be_enabled()
    expect(page.locator("#file-meta")).to_contain_text("00:00:03")
    page.locator("#diarize").check()
    page.locator("#timestamps").check()
    page.locator("#advanced summary").click()
    page.locator("#terms").fill("Deepgram\nNFS-e")
    expect(page.locator("#filler_words")).to_be_disabled()
    page.locator("#language").select_option("en")
    expect(page.locator("#filler_words")).to_be_enabled()
    page.locator("#filler_words").check()
    page.locator("#language").select_option("pt-BR")
    expect(page.locator("#filler_words")).not_to_be_checked()
    page.locator("#model").select_option("nova-2")
    assert page.locator('#language option[value="multi"]').count() == 0
    page.locator("#model").select_option("nova-3")
    page.locator("#advanced summary").click()
    balance_state["amount"] = "189.75"
    page.locator("#submit").click()
    expect(page.locator("#preview")).to_contain_text("[00:00:00 · Pessoa 1] Olá, Deepgram!")
    expect(page.locator("#submit")).to_be_enabled()
    expect(page.locator("#balance-value")).to_contain_text("189,75")
    assert len(calls) == 1
    sent = calls[0]
    assert sent["body"] == audio.getvalue(), "Body must be the audio bytes, unwrapped"
    assert sent["headers"]["content-type"] == "application/octet-stream"
    assert unquote(sent["headers"]["x-file-name"]) == "reunião.wav"
    assert json.loads(unquote(sent["headers"]["x-options"]))["terms"] == "Deepgram\nNFS-e"
    page.screenshot(path=str(OUTPUT / "desktop-result.png"), full_page=True)
    for format in ("txt", "md", "json"):
        page.locator("#format").select_option(format)
        with page.expect_download() as pending:
            page.locator("#download").click()
        download = pending.value
        assert download.suggested_filename == f"reunião.{format}"
        text = Path(download.path()).read_text()
        if format == "json":
            assert json.loads(text) == RESULT
            expect(page.locator("#timestamps")).to_be_disabled()
        elif format == "md":
            assert "**00:00:00 · Pessoa 1**" in text
        else:
            assert "Olá, Deepgram!" in text
    assert len(calls) == 1, "Downloads must not trigger another transcription"
    for width in (390, 768, 1024):
        page.set_viewport_size({"width": width, "height": 900})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), f"Overflow at {width}px"
    page.set_viewport_size({"width": 390, "height": 900})
    page.locator("#format").select_option("txt")
    page.screenshot(path=str(OUTPUT / "mobile-result.png"), full_page=True)
    page.locator("#clear").click()
    expect(page.locator("#preview")).to_be_hidden()
    expect(page.locator("#download")).to_be_disabled()
    expect(page.locator("#submit")).to_be_disabled()
    expect(page.locator("#file-title")).to_have_text("Selecione ou arraste um áudio")
    balance_state["error"] = "A chave atual não permite consultar o saldo. Use uma chave com billing:read."
    page.locator("#refresh-balance").click()
    expect(page.locator("#balance-value")).to_have_text("Indisponível")
    expect(page.locator("#balance-note")).to_contain_text("billing:read")
    page.unroute("**/api/transcribe", transcribe)
    page.route("**/api/transcribe", lambda route: route.fulfill(status=502, json={"error": "A chave da Deepgram foi recusada."}))
    page.locator("#file").set_input_files({"name": "teste.wav", "mimeType": "audio/wav", "buffer": audio.getvalue()})
    expect(page.locator("#submit")).to_be_enabled()
    page.locator("#submit").click()
    expect(page.locator("#error")).to_contain_text("chave da Deepgram foi recusada")
    expect(page.locator("#submit")).to_be_enabled()
    expect(page.locator("#progress-area")).to_be_hidden()
    page.reload()
    expect(page.locator("#preview")).to_be_hidden()
    expect(page.locator("#submit")).to_be_disabled()
    assert not errors, errors
    print("Browser OK: balance load/manual refresh/refresh after transcription/permission failure; setup, upload, language/model compatibility, transcript, three downloads from one request, clear, provider error, reload, responsive layouts. No real Deepgram request.")
    context.close()
    browser.close()
