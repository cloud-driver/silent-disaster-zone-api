import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.main import app
from src.auth.store import hash_password


class ApiAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

        self.auth_db_path = (
            Path(self.temp_dir.name)
            / "api_auth.sqlite3"
        )

        self.env_backup = {
            key: os.environ.get(key)
            for key in [
                "AUTH_DB_PATH",
                "AUTH_LOGIN_USERNAME",
                "AUTH_LOGIN_PASSWORD_HASH",
                "AUTH_STORAGE_SECRET",
                "AUTH_TRUST_PROXY_HEADERS",
            ]
        }

        os.environ["AUTH_DB_PATH"] = str(
            self.auth_db_path
        )

        os.environ["AUTH_LOGIN_USERNAME"] = (
            "test-admin"
        )

        os.environ["AUTH_LOGIN_PASSWORD_HASH"] = (
            hash_password("test-password")
        )

        os.environ["AUTH_STORAGE_SECRET"] = (
            "test-storage-secret"
        )

        os.environ["AUTH_TRUST_PROXY_HEADERS"] = "true"

        self.client = TestClient(app)

    def tearDown(self):
        for key, value in self.env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        self.temp_dir.cleanup()

    def login(self):
        response = self.client.post(
            "/auth/login",
            json={
                "username": "test-admin",
                "password": "test-password",
            },
            headers={
                "X-Forwarded-For": "203.0.113.10",
            },
        )

        self.assertEqual(response.status_code, 200)

        return response.json()["access_token"]

    def auth_headers(self, token):
        return {
            "Authorization": f"Bearer {token}",
        }

    def test_health_routes_do_not_need_token(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)

    def test_regular_api_requires_token(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 401)

        token = self.login()

        response = self.client.get(
            "/",
            headers=self.auth_headers(token),
        )

        self.assertEqual(response.status_code, 200)

    def test_login_returns_15_minute_token(self):
        token = self.login()

        response = self.client.get(
            "/auth/session",
            headers=self.auth_headers(token),
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertEqual(
            payload["status"],
            "authenticated",
        )

        self.assertLessEqual(
            payload["expires_in"],
            900,
        )

        self.assertGreater(
            payload["expires_in"],
            0,
        )

    def test_logout_revokes_token(self):
        token = self.login()

        response = self.client.post(
            "/auth/logout",
            headers=self.auth_headers(token),
        )

        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            "/",
            headers=self.auth_headers(token),
        )

        self.assertEqual(response.status_code, 401)

    def test_same_ip_is_limited_to_five_logins_per_minute(self):
        headers = {
            "X-Forwarded-For": "198.51.100.21",
        }

        for _ in range(5):
            response = self.client.post(
                "/auth/login",
                json={
                    "username": "test-admin",
                    "password": "wrong-password",
                },
                headers=headers,
            )

            self.assertEqual(response.status_code, 401)

        blocked_response = self.client.post(
            "/auth/login",
            json={
                "username": "test-admin",
                "password": "wrong-password",
            },
            headers=headers,
        )

        self.assertEqual(
            blocked_response.status_code,
            429,
        )

        self.assertIn(
            "Retry-After",
            blocked_response.headers,
        )

    def test_openapi_marks_bearer_security(self):
        response = self.client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)

        schema = response.json()

        silent_risk_security = schema["paths"][
            "/silent-risk"
        ]["get"]["security"]

        self.assertEqual(
            silent_risk_security,
            [{"BearerAccessToken": []}],
        )

        admin_security = schema["paths"][
            "/reports/pending"
        ]["get"]["security"]

        self.assertEqual(
            admin_security,
            [
                {
                    "BearerAccessToken": [],
                    "ReportAdminKey": [],
                }
            ],
        )

        login_operation = schema["paths"][
            "/auth/login"
        ]["post"]

        self.assertNotIn(
            "security",
            login_operation,
        )


if __name__ == "__main__":
    unittest.main()