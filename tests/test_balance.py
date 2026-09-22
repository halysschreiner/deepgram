import unittest
from unittest.mock import MagicMock, patch

import requests

import app as server


class BalanceTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()
        for name, value in (("API_KEY", "secret-balance-key"), ("PROJECT_ID", "")):
            patcher = patch.object(server, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.headers = {"X-App-Token": server.TOKEN}

    def response(self, body, status=200):
        response = MagicMock()
        response.status_code = status
        response.json.return_value = body
        response.__enter__.return_value = response
        return response

    def projects(self):
        return self.response({"projects": [{"project_id": "project-test"}]})

    @patch("app.requests.get")
    def test_sum_by_currency_and_do_not_expose_credentials(self, get):
        get.side_effect = [self.projects(), self.response({"balances": [
            {"amount": 100.1, "units": "usd"}, {"amount": 0.2, "units": "USD"},
            {"amount": 5, "units": "EUR"},
        ]})]
        response = self.client.get("/api/balance", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json["balances"], [{"amount": "5", "units": "EUR"}, {"amount": "100.3", "units": "USD"}])
        self.assertIn("checked_at", response.json)
        self.assertNotIn(server.API_KEY, response.text)
        self.assertNotIn("project-test", response.text)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args.args[0], "https://api.deepgram.com/v1/projects/project-test/balances")
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    @patch("app.requests.get")
    def test_zero_and_negative_balances_are_valid(self, get):
        with patch.object(server, "PROJECT_ID", "project-test"):
            for amount in (0, -0.125):
                get.return_value = self.response({"balances": [{"amount": amount, "units": "USD"}]})
                response = self.client.get("/api/balance", headers=self.headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json["balances"][0]["amount"], str(amount))

    @patch("app.requests.get")
    def test_optional_project_and_refresh_use_current_provider_balance(self, get):
        get.side_effect = [self.response({"balances": [{"amount": 200, "units": "USD"}]}),
                           self.response({"balances": [{"amount": 199, "units": "USD"}]})]
        with patch.object(server, "PROJECT_ID", "project-test"):
            self.assertEqual(self.client.get("/api/balance", headers=self.headers).json["balances"][0]["amount"], "200")
            self.assertEqual(self.client.get("/api/balance", headers=self.headers).json["balances"][0]["amount"], "199")
        self.assertEqual(get.call_count, 2)

    @patch("app.requests.get")
    def test_missing_key_and_token_do_not_make_external_calls(self, get):
        self.assertEqual(self.client.get("/api/balance").status_code, 403)
        with patch.object(server, "API_KEY", ""):
            self.assertEqual(self.client.get("/api/balance", headers=self.headers).status_code, 503)
        get.assert_not_called()

    @patch("app.requests.get")
    def test_ambiguous_project_is_not_selected_arbitrarily(self, get):
        get.return_value = self.response({"projects": [{"project_id": "a"}, {"project_id": "b"}]})
        response = self.client.get("/api/balance", headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertIn("DEEPGRAM_PROJECT_ID", response.json["error"])
        get.assert_called_once()
        get.reset_mock()
        with patch.object(server, "PROJECT_ID", "../other-endpoint"):
            self.assertEqual(self.client.get("/api/balance", headers=self.headers).status_code, 400)
        get.assert_not_called()

    @patch("app.requests.get")
    def test_permissions_authentication_and_rate_limits(self, get):
        with patch.object(server, "PROJECT_ID", "project-test"):
            for status, expected in ((403, "billing:read"), (401, "chave"), (429, "Limite"), (500, "Deepgram")):
                with self.subTest(status=status):
                    get.return_value = self.response({"error": server.API_KEY}, status)
                    response = self.client.get("/api/balance", headers=self.headers)
                    self.assertEqual(response.status_code, 502)
                    self.assertIn(expected, response.json["error"])
                    self.assertNotIn(server.API_KEY, response.text)
                    self.assertNotIn("balances", response.json)

    @patch("app.requests.get")
    def test_empty_or_malformed_result_never_appears_as_zero(self, get):
        with patch.object(server, "PROJECT_ID", "project-test"):
            for data in ({}, {"balances": []}, {"balances": [{}]}, {"balances": [None]},
                         {"balances": [{"amount": "NaN", "units": "USD"}]},
                         {"balances": [{"amount": True, "units": "USD"}]},
                         {"balances": [{"amount": 3, "units": None}]},
                         {"balances": [{"amount": "Infinity", "units": "USD"}]}):
                with self.subTest(data=data):
                    get.return_value = self.response(data)
                    response = self.client.get("/api/balance", headers=self.headers)
                    self.assertEqual(response.status_code, 502)
                    self.assertNotIn("balances", response.json)

    @patch("app.requests.get")
    def test_network_failure_does_not_affect_transcription_state(self, get):
        for failure, status in ((requests.Timeout(), 504), (requests.ConnectionError(), 502)):
            get.side_effect = failure
            response = self.client.get("/api/balance", headers=self.headers)
            self.assertEqual(response.status_code, status)
            self.assertFalse(server.BUSY.locked())
            self.assertTrue(self.client.get("/api/config").json["configured"])


if __name__ == "__main__":
    unittest.main()
