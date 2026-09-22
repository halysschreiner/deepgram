"""Local-only, ephemeral proxy to Deepgram's prerecorded API."""

import json
import os
import re
import secrets
import threading
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from catalog import LANGUAGES, MODELS, PRICING, build_params

MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "500"))
API_KEY = os.environ.get("DEEPGRAM_API_KEY", "").strip()
PROJECT_ID = os.environ.get("DEEPGRAM_PROJECT_ID", "").strip()
TIMEOUT = int(os.environ.get("DEEPGRAM_TIMEOUT_SECONDS", "1800"))
ALLOWED_HOSTS = {h.strip().lower() for h in
                 os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,::1").split(",") if h.strip()}
if not 1 <= MAX_MB <= 2048 or not 30 <= TIMEOUT <= 3300:
    raise RuntimeError("MAX_UPLOAD_MB deve estar entre 1 e 2048; timeout entre 30 e 3300 segundos.")
TOKEN = secrets.token_urlsafe(32)
BUSY = threading.Lock()
EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac", ".aac", ".mp4", ".webm", ".aiff", ".aif", ".amr", ".wma"}
app = Flask(__name__, static_url_path="/static")
app.config.update(MAX_CONTENT_LENGTH=(MAX_MB * 1024 * 1024) + 64 * 1024,
                  MAX_FORM_MEMORY_SIZE=512 * 1024, MAX_FORM_PARTS=4)


@app.before_request
def local_only():
    # Bind restriction is in compose; Host validation also prevents DNS rebinding.
    host = urlsplit("//" + request.host).hostname
    if host is None or host.lower() not in ALLOWED_HOSTS:
        return jsonify(error="Host não permitido. Veja ALLOWED_HOSTS."), 403
    if request.method == "POST" or request.path == "/api/balance":
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            return jsonify(error="Origem não permitida."), 403
        if not secrets.compare_digest(request.headers.get("X-App-Token", ""), TOKEN):
            return jsonify(error="Atualize a página antes de continuar."), 403


@app.after_request
def response_headers(response):
    response.headers.update({
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
    })
    return response


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/api/config")
def config():
    return jsonify(configured=bool(API_KEY), token=TOKEN, max_upload_mb=MAX_MB,
                   timeout_seconds=TIMEOUT, models=MODELS,
                   languages=[{"id": code, "name": name} for code, name in LANGUAGES],
                   pricing=PRICING)


class BalanceError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def balance_get(path):
    # Only read-only management endpoints; credentials and raw responses stay here.
    with requests.get("https://api.deepgram.com/v1/" + path,
                      headers={"Authorization": "Token " + API_KEY},
                      timeout=(5, 10), allow_redirects=False) as response:
        if response.status_code == 401:
            raise BalanceError("A chave foi recusada. Confira DEEPGRAM_API_KEY no .env e recrie o container.")
        if response.status_code == 403:
            raise BalanceError("A chave atual não permite consultar o saldo. Use uma chave com billing:read e project:read no .env e recrie o container.")
        if response.status_code == 429:
            raise BalanceError("Limite de consultas atingido. Aguarde antes de atualizar o saldo.")
        if response.status_code != 200:
            raise BalanceError("A Deepgram não disponibilizou o saldo. Consulte o console ou tente atualizar mais tarde.")
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Invalid provider response")
        return data


@app.get("/api/balance")
def balance():
    if not API_KEY:
        return jsonify(error="Configure DEEPGRAM_API_KEY no .env para consultar os créditos."), 503
    try:
        project_id = PROJECT_ID
        if not project_id:
            projects = balance_get("projects").get("projects")
            if not isinstance(projects, list):
                raise ValueError("Invalid project list")
            if len(projects) != 1:
                raise BalanceError("Não foi possível selecionar um único projeto. Preencha DEEPGRAM_PROJECT_ID no .env com o projeto usado nas transcrições e recrie o container.", 409)
            project_id = projects[0].get("project_id") if isinstance(projects[0], dict) else None
        if not isinstance(project_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", project_id):
            raise BalanceError("Não foi possível identificar o projeto. Confira DEEPGRAM_PROJECT_ID no .env.", 400)
        balances = balance_get(f"projects/{project_id}/balances").get("balances")
        if not isinstance(balances, list):
            raise ValueError("Invalid balance list")
        if not balances:
            raise BalanceError("A Deepgram não retornou saldos para este projeto. Confira o console.")
        totals = {}
        for item in balances:
            if not isinstance(item, dict) or isinstance(item.get("amount"), bool):
                raise ValueError("Invalid balance")
            amount = Decimal(str(item.get("amount")))
            units = item.get("units")
            if not amount.is_finite() or abs(amount) > Decimal("1e15") or not isinstance(units, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,16}", units):
                raise ValueError("Invalid balance amount or units")
            units = units.upper()
            totals[units] = totals.get(units, Decimal("0")) + amount
        return jsonify(balances=[{"amount": str(amount), "units": units} for units, amount in sorted(totals.items())],
                       checked_at=datetime.now(timezone.utc).isoformat())
    except BalanceError as failure:
        return jsonify(error=str(failure)), failure.status
    except requests.Timeout:
        return jsonify(error="A consulta de saldo demorou demais. Tente atualizar novamente."), 504
    except requests.RequestException:
        return jsonify(error="Não foi possível conectar à Deepgram para consultar o saldo."), 502
    except (ValueError, InvalidOperation, TypeError):
        return jsonify(error="A Deepgram retornou um saldo inesperado. Confira o console."), 502


def provider_error(response):
    messages = {
        400: "A Deepgram recusou o arquivo ou as opções. Confira o formato e a combinação de idioma e modelo.",
        401: "A chave da Deepgram foi recusada. Confira DEEPGRAM_API_KEY no .env e recrie o container.",
        402: "A Deepgram informou que não há créditos suficientes. Confira o saldo no console.",
        403: "A chave não tem permissão para esta operação ou este modelo.",
        413: "O arquivo ultrapassa o limite aceito pela Deepgram.",
        429: "A Deepgram atingiu um limite de uso. Aguarde antes de tentar novamente.",
    }
    message = messages.get(response.status_code, "A Deepgram não concluiu a transcrição. Tente novamente mais tarde.")
    request_id = response.headers.get("dg-request-id", "")
    error_code = ""
    try:
        body = response.json()
        if isinstance(body, dict):
            request_id = body.get("request_id", request_id)
            error_code = str(body.get("err_code", ""))[:100]
            if "keyterm" in str(body.get("err_msg", "")).lower():
                message += " Reduza os termos específicos; o Nova-3 aceita até 500 tokens."
    except ValueError:
        pass
    # Never return/log arbitrary provider messages: they can echo secrets or audio content.
    return jsonify(error=message, provider_status=response.status_code,
                   request_id=str(request_id)[:100], code=error_code), 502


@app.post("/api/transcribe")
def transcribe():
    if not API_KEY:
        return jsonify(error="Preencha DEEPGRAM_API_KEY no .env e execute docker compose up -d --force-recreate."), 503
    if not BUSY.acquire(blocking=False):
        return jsonify(error="Já existe uma transcrição em andamento. Aguarde a conclusão."), 409
    try:
        # The body is the raw audio: nothing is buffered to memory or to /tmp, so the
        # ceiling is Deepgram's 2 GB and not the size of the container's tmpfs.
        options = json.loads(unquote(request.headers.get("X-Options", "{}")))
        params = build_params(options)
        if Path(unquote(request.headers.get("X-File-Name", ""))).suffix.lower() not in EXTENSIONS:
            return jsonify(error="Formato não suportado. Use MP3, WAV, M4A, OGG, OPUS, FLAC ou outro formato listado na tela."), 400
        size = request.content_length
        if size is None:
            return jsonify(error="O envio precisa informar o tamanho do arquivo."), 411
        if not size:
            return jsonify(error="O arquivo está vazio."), 400
        if size > MAX_MB * 1024 * 1024:
            return jsonify(error=f"Selecione um arquivo de até {MAX_MB} MB."), 413
        # Raw binary streaming, no multipart wrapper upstream, no automatic retries.
        upstream = requests.Request(
            "POST", "https://api.deepgram.com/v1/listen", params=params,
            headers={"Authorization": "Token " + API_KEY, "Content-Type": "application/octet-stream"},
            data=request.stream,
        ).prepare()
        # requests cannot measure a socket, and would fall back to chunked encoding.
        upstream.headers.pop("Transfer-Encoding", None)
        upstream.headers["Content-Length"] = str(size)
        with requests.Session() as session, session.send(
            upstream, timeout=(20, TIMEOUT), allow_redirects=False,
            # send() skips the env lookup that requests.post() does, and dropping it
            # would silently ignore HTTPS_PROXY, NO_PROXY and REQUESTS_CA_BUNDLE.
            **session.merge_environment_settings(upstream.url, {}, None, None, None),
        ) as response:
            if response.status_code != 200:
                return provider_error(response)
            try:
                result = response.json()
            except ValueError:
                return jsonify(error="A Deepgram retornou uma resposta ilegível. O áudio pode já ter sido cobrado; confira o console antes de reenviar."), 502
            if not isinstance(result, dict) or not isinstance(result.get("results"), dict) or not isinstance(result["results"].get("channels"), list):
                return jsonify(error="A Deepgram retornou um resultado inesperado. Confira o console antes de reenviar."), 502
            return jsonify(result=result)
    except json.JSONDecodeError:
        return jsonify(error="As opções enviadas não são JSON válido."), 400
    except (ValueError, TypeError) as error:
        return jsonify(error=str(error) if isinstance(error, ValueError) else "Formato inválido nas opções."), 400
    except requests.Timeout:
        return jsonify(error="O tempo de espera terminou. A Deepgram pode ter processado e cobrado o áudio; confira o console antes de reenviar."), 504
    except requests.RequestException:
        return jsonify(error="A conexão com a Deepgram falhou. Se o envio já começou, confira o console antes de reenviar: o áudio pode ter sido cobrado."), 502
    finally:
        BUSY.release()


@app.errorhandler(HTTPException)
def http_error(error):
    message = f"O envio ultrapassou o limite de {MAX_MB} MB." if error.code == 413 else "Requisição inválida ou endereço não encontrado."
    return jsonify(error=message), error.code


@app.errorhandler(Exception)
def unexpected_error(error):
    # Do not log audio, credentials, filenames or transcripts.
    app.logger.error("Falha interna: %s", type(error).__name__)
    return jsonify(error="Não foi possível concluir a operação. Confira o estado do container antes de tentar novamente."), 500
