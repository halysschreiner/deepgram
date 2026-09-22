import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import app as server


class SettingsTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "settings" / "credentials.json"
        for name, value in (("SETTINGS_FILE", self.path), ("API_KEY", "environment-key"),
                            ("PROJECT_ID", "environment-project")):
            patcher = patch.object(server, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = server.app.test_client()
        self.headers = {"X-App-Token": server.TOKEN}

    def save(self, key="new-key", project="", **kwargs):
        return self.client.post("/api/settings", json={"api_key": key, "project_id": project},
                                headers=kwargs.pop("headers", self.headers), **kwargs)

    def provider(self, body):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = body
        response.__enter__.return_value = response
        return response

    def test_environment_fallback_and_first_setup(self):
        self.assertEqual(server.get_credentials(), {"api_key": "environment-key", "project_id": "environment-project"})
        with patch.object(server, "API_KEY", ""):
            self.assertFalse(self.client.get("/api/config").json["configured"])
            self.assertEqual(self.save(key="").status_code, 400)
            self.assertEqual(self.save().status_code, 200)
            self.assertTrue(self.client.get("/api/config").json["configured"])

    def test_private_persistent_file_wins_over_environment_after_restart(self):
        response = self.save(key="  new-key  ", project=" new-project ")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("new-key", response.text)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        env = {**os.environ, "SETTINGS_FILE": str(self.path), "DEEPGRAM_API_KEY": "old-key"}
        restarted = subprocess.run([sys.executable, "-c",
            "import app; assert app.get_credentials() == {'api_key': 'new-key', 'project_id': 'new-project'}"],
            env=env, capture_output=True)
        self.assertEqual(restarted.returncode, 0)
        config = self.client.get("/api/config")
        self.assertEqual(config.json["project_id"], "new-project")
        self.assertNotIn("new-key", config.text)
        self.assertEqual(self.client.get("/data/credentials.json").status_code, 404)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_blank_key_keeps_current_key_and_can_clear_project(self):
        self.assertEqual(self.save(key="", project="other-project").status_code, 200)
        self.assertEqual(server.get_credentials()["api_key"], "environment-key")
        self.assertEqual(self.save(key="").status_code, 200)
        self.assertEqual(server.get_credentials()["project_id"], "")

    def test_host_origin_and_token_protect_mutation(self):
        for headers in ({}, {"X-App-Token": "wrong"},
                        {**self.headers, "Origin": "https://attacker.test"},
                        {**self.headers, "Host": "attacker.test"}):
            self.assertEqual(self.save(headers=headers).status_code, 403)
        self.assertFalse(self.path.exists())

    def test_malformed_or_oversized_input_keeps_previous_credentials(self):
        self.save()
        for key, project in ((None, ""), ([], ""), (123, ""), ("x\ny", ""), ("á", ""),
                             ("x" * 513, ""), ("key with spaces", ""),
                             ("x", "../project"), ("x", None), ("x", "x" * 101)):
            self.assertEqual(self.save(key=key, project=project).status_code, 400)
        for data in (None, [], {}, {"api_key": "key"}, {"api_key": "key", "project_id": "", "extra": True}):
            response = self.client.post("/api/settings", data=json.dumps(data),
                                        content_type="application/json", headers=self.headers)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.save(key="x" * 5000).status_code, 413)
        self.assertEqual(server.get_credentials()["api_key"], "new-key")

    def test_write_failure_preserves_previous_configuration(self):
        self.save()
        with patch("app.os.replace", side_effect=OSError("secret must not leak")):
            response = self.save(key="replacement-key")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret", response.text)
        self.assertEqual(server.get_credentials()["api_key"], "new-key")
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_corrupt_file_never_silently_uses_environment_account(self):
        self.save()
        self.path.write_text("invalid JSON")
        with patch("app.requests.Session.send") as send:
            self.assertEqual(self.client.post("/api/transcribe", headers=self.headers).status_code, 500)
            send.assert_not_called()

    @patch("app.requests.Session.send")
    def test_inflight_transcription_keeps_key_and_next_upload_uses_new_key(self, send):
        seen = []
        def capture(prepared, **kwargs):
            seen.append(prepared.headers["Authorization"])
            self.assertEqual(self.save(key="replacement-key").status_code, 200)
            return self.provider({"results": {"channels": []}})
        send.side_effect = capture
        for _ in range(2):
            response = self.client.post("/api/transcribe", headers={**self.headers, "X-File-Name": "test.mp3"}, data=b"audio")
            self.assertEqual(response.status_code, 200)
        self.assertEqual(seen, ["Token environment-key", "Token replacement-key"])

    @patch("app.requests.get")
    def test_balance_uses_one_credentials_snapshot_during_rotation(self, get):
        self.save(key="first-key")
        seen = []
        def capture(url, **kwargs):
            seen.append(kwargs["headers"]["Authorization"])
            if url.endswith("/projects"):
                self.save(key="second-key", project="second-project")
                return self.provider({"projects": [{"project_id": "first-project"}]})
            return self.provider({"balances": [{"amount": 10, "units": "USD"}]})
        get.side_effect = capture
        self.assertEqual(self.client.get("/api/balance", headers=self.headers).status_code, 200)
        self.assertEqual(seen, ["Token first-key", "Token first-key"])
        self.assertEqual(self.client.get("/api/balance", headers=self.headers).status_code, 200)
        self.assertEqual(seen[-1], "Token second-key")
        self.assertTrue(get.call_args.args[0].endswith("second-project/balances"))
