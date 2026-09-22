"""Real settings API with isolated storage and mocked Deepgram; no live credentials."""
import io
import os
from pathlib import Path
import sys
import tempfile
import threading
import wave
from unittest.mock import MagicMock, patch

from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as server


def provider(body):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = body
    response.__enter__.return_value = response
    return response


audio = io.BytesIO()
with wave.open(audio, "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(8000)
    wav.writeframes(b"\0\0" * 8000)

with tempfile.TemporaryDirectory() as folder, \
        patch.object(server, "SETTINGS_FILE", Path(folder) / "credentials.json"), \
        patch.object(server, "API_KEY", ""), patch.object(server, "PROJECT_ID", ""), \
        patch("app.requests.get") as get, patch("app.requests.Session.send") as send:
    def balance(url, **kwargs):
        if url.endswith("/projects"):
            return provider({"projects": [{"project_id": "test-project"}]})
        return provider({"balances": [{"amount": "12.34", "units": "USD"}]})
    get.side_effect = balance
    send.return_value = provider({"results": {"channels": [{"alternatives": [{"transcript": "Texto preservado."}]}]}})
    http = make_server("127.0.0.1", 0, server.app, threaded=True)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            launch = {"headless": True}
            if os.environ.get("CHROMIUM_EXECUTABLE"):
                launch["executable_path"] = os.environ["CHROMIUM_EXECUTABLE"]
            browser = playwright.chromium.launch(**launch)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{http.server_port}")
            expect(page.locator("#setup")).to_be_visible()
            page.locator("#file").set_input_files({"name": "test.wav", "mimeType": "audio/wav", "buffer": audio.getvalue()})
            expect(page.locator("#submit")).to_be_disabled()
            page.locator("#open-settings").click()
            expect(page.locator("#api-key")).to_be_focused()
            page.locator("#api-key").fill("first-browser-key")
            page.locator("#save-settings").click()
            expect(page.locator("#settings-dialog")).not_to_be_visible()
            expect(page.locator("#setup")).not_to_be_visible()
            expect(page.locator("#balance-value")).to_contain_text("12,34")
            expect(page.locator("#submit")).to_be_enabled()
            page.locator("#submit").click()
            expect(page.locator("#preview")).to_contain_text("Texto preservado.")
            assert send.call_args.args[0].headers["Authorization"] == "Token first-browser-key"

            page.locator("#open-settings").click()
            expect(page.locator("#api-key")).to_have_value("")
            page.locator("#api-key").fill("second-browser-key")
            page.locator("#project-id").fill("another-project")
            page.locator("#save-settings").click()
            expect(page.locator("#settings-dialog")).not_to_be_visible()
            expect(page.locator("#preview")).to_contain_text("Texto preservado.")
            expect(page.locator("#file-title")).to_have_text("test.wav")
            expect(page.locator("#balance-value")).to_contain_text("12,34")
            assert get.call_args.kwargs["headers"]["Authorization"] == "Token second-browser-key"
            page.locator("#submit").click()
            expect(page.locator("#preview")).to_contain_text("Texto preservado.")
            assert send.call_args.args[0].headers["Authorization"] == "Token second-browser-key"

            page.locator("#open-settings").click()
            expect(page.locator("#project-id")).to_have_value("another-project")
            page.locator("#api-key").fill("invalid key with spaces")
            page.locator("#save-settings").click()
            expect(page.locator("#credentials-error")).to_be_visible()
            expect(page.locator("#api-key")).to_have_value("")
            assert server.get_credentials()["api_key"] == "second-browser-key"
            page.locator("#api-key").fill("unsaved-key")
            page.keyboard.press("Escape")
            expect(page.locator("#settings-dialog")).not_to_be_visible()
            expect(page.locator("#open-settings")).to_be_focused()
            expect(page.locator("#api-key")).to_have_value("")
            page.reload()
            expect(page.locator("#connection")).to_have_text("Chave configurada")
            page.locator("#open-settings").click()
            expect(page.locator("#api-key")).to_have_value("")
            expect(page.locator("#project-id")).to_have_value("another-project")
            page.locator("#project-id").fill("")
            page.locator("#save-settings").click()
            expect(page.locator("#settings-dialog")).not_to_be_visible()
            assert server.get_credentials() == {"api_key": "second-browser-key", "project_id": ""}
            assert "browser-key" not in page.evaluate("JSON.stringify({...localStorage, ...sessionStorage})")

            page.locator("#open-settings").click()
            Path("test-results").mkdir(exist_ok=True)
            for width, theme in ((1440, "light"), (390, "dark"), (320, "light")):
                page.set_viewport_size({"width": width, "height": 900})
                page.evaluate("theme => document.documentElement.dataset.theme = theme", theme)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                bounds = page.locator("#settings-dialog").bounding_box()
                assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width
                page.screenshot(path=f"test-results/settings-{width}-{theme}.png")
            assert not errors, errors
            browser.close()
    finally:
        http.shutdown()
        thread.join()
print("Browser settings OK: initial setup, live key rotation, balance, preserved transcript/file, errors, Escape/focus, reload, project-only change, private storage, mobile and themes. No real Deepgram request.")
