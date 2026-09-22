import io
import json
import os
import unittest
from urllib.parse import quote
from unittest.mock import MagicMock, patch

import requests

import app as server
from catalog import build_params

RESULT = {
    "metadata": {"request_id": "test-only", "duration": 2.4, "channels": 1},
    "results": {
        "channels": [{"alternatives": [{"transcript": "Olá, Deepgram!", "confidence": 0.98}]}],
        "utterances": [{"start": 0.0, "end": 2.4, "speaker": 0, "channel": 0, "transcript": "Olá, Deepgram!"}],
    },
}


class ParametersTests(unittest.TestCase):
    def test_default_and_model_compatibility(self):
        self.assertEqual(dict(build_params({}))["language"], "pt-BR")
        with self.assertRaises(ValueError):
            build_params({"model": "nova-2", "language": "multi"})
        with self.assertRaises(ValueError):
            build_params({"model": "flux-general-en"})

    def test_language_detection_excludes_language(self):
        params = dict(build_params({"language": "auto"}))
        self.assertEqual(params["detect_language"], "true")
        self.assertNotIn("language", params)

    def test_repeated_keyterms_and_legacy_keywords(self):
        params = build_params({"terms": "Deepgram\nnota fiscal\nDeepgram", "replacements": "deep gram => Deepgram"})
        self.assertEqual([value for key, value in params if key == "keyterm"], ["Deepgram", "nota fiscal"])
        self.assertIn(("replace", "deep gram:Deepgram"), params)
        self.assertIn(("keywords", "Deepgram"), build_params({"model": "nova-2", "terms": "Deepgram"}))

    def test_invalid_options_cannot_reach_provider(self):
        for options in ({"punctuate": "false"}, {"utt_split": float("nan")}, {"utt_split": True},
                        {"utt_split": 0}, {"terms": "word:2"}, {"replacements": "missing arrow"},
                        {"callback": "https://example.org"}, {"filler_words": True},
                        {"terms": "\n".join(str(n) for n in range(51))}, [], {"language": "invented"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                build_params(options)

    def test_diarization_uses_only_new_parameter(self):
        params = dict(build_params({"diarize_model": "v2"}))
        self.assertEqual(params["diarize_model"], "v2")
        self.assertNotIn("diarize", params)


class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()
        self.key = patch.object(server, "API_KEY", "test-secret-do-not-expose")
        self.key.start()
        self.addCleanup(self.key.stop)
        self.headers = {"X-App-Token": server.TOKEN}

    def upload(self, options=None, content=b"test audio", filename="audio.mp3", headers=None):
        # The audio is the whole body; name and options ride url-encoded in headers.
        sent = dict(self.headers if headers is None else headers)
        sent.setdefault("Content-Type", "application/octet-stream")
        sent.setdefault("X-File-Name", quote(filename))
        sent.setdefault("X-Options", quote(json.dumps(options or {})))
        return self.client.post("/api/transcribe", headers=sent, data=content)

    def sent_request(self, send):
        return send.call_args.args[0]

    def provider(self, status=200, body=RESULT):
        response = MagicMock()
        response.status_code = status
        response.headers = {"dg-request-id": "req-test"}
        response.json.return_value = body
        response.__enter__.return_value = response
        return response

    def test_public_config_does_not_expose_key_and_is_not_cached(self):
        response = self.client.get("/api/config")
        self.assertTrue(response.json["configured"])
        self.assertNotIn(server.API_KEY, response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(self.client.get("/.env").status_code, 404)

    def test_host_origin_and_csrf_validation(self):
        self.assertEqual(self.client.get("/api/config", headers={"Host": "attacker.test"}).status_code, 403)
        self.assertEqual(self.upload(headers={}).status_code, 403)
        self.assertEqual(self.upload(headers={**self.headers, "Origin": "https://attacker.test"}).status_code, 403)
        self.assertEqual(self.client.get("/health").status_code, 200)

    @patch("app.requests.Session.send")
    def test_empty_missing_and_wrong_extension(self, send):
        self.assertEqual(self.upload(content=b"").status_code, 411)  # no Content-Length at all
        declared_empty = self.client.post(  # browsers do send Content-Length: 0
            "/api/transcribe", headers={**self.headers, "X-File-Name": "a.mp3"},
            data=b"", environ_overrides={"CONTENT_LENGTH": "0"})
        self.assertEqual(declared_empty.status_code, 400)
        self.assertEqual(self.upload(filename="test.exe").status_code, 400)
        self.assertEqual(self.upload(filename="sem-extensao").status_code, 400)
        self.assertEqual(self.client.post("/api/transcribe", headers=self.headers).status_code, 400)
        send.assert_not_called()
        self.assertFalse(server.BUSY.locked())

    @patch("app.requests.Session.send")
    def test_accented_filename_and_keyterms_survive_header_encoding(self, send):
        send.return_value = self.provider()
        response = self.upload(options={"model": "nova-3", "terms": "ação\nRibeirão"},
                               filename="reunião gravação.mp4")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("keyterm=a%C3%A7%C3%A3o", self.sent_request(send).url)

    @patch("app.requests.Session.send")
    def test_proxy_and_ca_bundle_environment_is_honoured(self, send):
        # send() on a hand-prepared request bypasses the env lookup requests.post() does.
        send.return_value = self.provider()
        with patch.dict("os.environ", {"HTTPS_PROXY": "http://proxy.test:3128",
                                       "REQUESTS_CA_BUNDLE": "/certs/ca.pem"}):
            self.assertEqual(self.upload().status_code, 200)
        self.assertEqual(send.call_args.kwargs["proxies"]["https"], "http://proxy.test:3128")
        self.assertEqual(send.call_args.kwargs["verify"], "/certs/ca.pem")

    def test_worst_case_options_fit_the_gunicorn_header_budget(self):
        # terms (2000) + replacements (4000) all accented is the largest X-Options possible.
        options = json.dumps({"terms": "ç" * 2000, "replacements": "ã" * 4000})
        self.assertLess(len(quote(options)), 65536)

    @patch("app.requests.Session.send")
    def test_success_streams_body_upstream_without_buffering(self, send):
        content = b"wave" * 300_000
        seen = {}
        def capture(prepared, **kwargs):
            seen["body"] = prepared.body
            seen["headers"] = prepared.headers
            seen["kwargs"] = kwargs
            return self.provider()
        send.side_effect = capture
        response = self.upload(content=content)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json["result"], RESULT)
        # The body must stay a stream: a bytes body here would mean the file was buffered.
        self.assertTrue(hasattr(seen["body"], "read"))
        self.assertEqual(seen["body"].read(), content)
        self.assertEqual(seen["headers"]["Content-Length"], str(len(content)))
        self.assertNotIn("Transfer-Encoding", seen["headers"])
        self.assertEqual(seen["headers"]["Authorization"], "Token " + server.API_KEY)
        self.assertFalse(seen["kwargs"]["allow_redirects"])
        send.assert_called_once()
        self.assertFalse(server.BUSY.locked())

    def test_upload_ceiling_matches_provider_maximum(self):
        for value, valid in ((2048, True), (2049, False), (0, False)):
            with self.subTest(value=value), patch.dict("os.environ", {"MAX_UPLOAD_MB": str(value)}):
                ok = 1 <= int(os.environ["MAX_UPLOAD_MB"]) <= 2048
                self.assertEqual(ok, valid)

    @patch("app.requests.Session.send")
    def test_missing_key_oversized_upload_and_invalid_json(self, send):
        with patch.object(server, "API_KEY", ""):
            self.assertEqual(self.upload().status_code, 503)
        with patch.dict(server.app.config, MAX_CONTENT_LENGTH=1024):
            self.assertEqual(self.upload(content=b"x" * 2048).status_code, 413)
        with patch.object(server, "MAX_MB", 1):
            self.assertEqual(self.upload(content=b"x" * (2 * 1024 * 1024)).status_code, 413)
        self.assertEqual(self.upload(headers={**self.headers, "X-Options": "bad"}).status_code, 400)
        send.assert_not_called()
        self.assertFalse(server.BUSY.locked())

    @patch("app.requests.Session.send")
    def test_busy_returns_without_second_billable_request(self, send):
        server.BUSY.acquire()
        try:
            self.assertEqual(self.upload().status_code, 409)
        finally:
            server.BUSY.release()
        send.assert_not_called()

    @patch("app.requests.Session.send")
    def test_provider_errors_and_no_automatic_retries(self, send):
        for status in (400, 401, 402, 403, 413, 429, 500):
            with self.subTest(status=status):
                send.reset_mock()
                send.return_value = self.provider(status, {"err_msg": server.API_KEY, "err_code": "TEST_ERROR"})
                response = self.upload()
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json["provider_status"], status)
                self.assertNotIn(server.API_KEY, response.text)
                self.assertFalse(server.BUSY.locked())
                send.assert_called_once()

    @patch("app.requests.Session.send")
    def test_timeout_and_connection_error_release_lock(self, send):
        for exception, status in ((requests.Timeout(), 504), (requests.ConnectionError(), 502)):
            with self.subTest(status=status):
                send.side_effect = exception
                response = self.upload()
                self.assertEqual(response.status_code, status)
                self.assertIn("cobrad", response.json["error"])
                self.assertFalse(server.BUSY.locked())

    @patch("app.requests.Session.send")
    def test_unexpected_provider_json(self, send):
        send.return_value = self.provider(body={"unexpected": True})
        self.assertEqual(self.upload().status_code, 502)
        send.return_value.json.side_effect = ValueError()
        self.assertEqual(self.upload().status_code, 502)
        self.assertFalse(server.BUSY.locked())


if __name__ == "__main__":
    unittest.main()
