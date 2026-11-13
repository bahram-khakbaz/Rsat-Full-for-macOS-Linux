import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402

from app import main as worker  # noqa: E402

IDENTITY = {"runAs": "EXAMPLE\\rsatWorker$", "computer": "TEST-HOST", "domain": "example.com"}
CODE = "test-only-pairing-code"


class UnattendedPairingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.code_file = Path(self.directory.name) / "pairing-code.txt"
        self.code_file.write_text(CODE)
        worker._pairing_started = time.monotonic()
        worker._pairing_used = False
        worker._pairing_attempts = 0
        worker._modules_cache = None
        worker.settings.pairing_code = CODE
        worker.settings.agent_token = "test-only-channel-credential" * 2
        worker.settings.pairing_code_file = str(self.code_file)
        self.mock = patch.object(worker, "run_ps", return_value=IDENTITY)
        self.runner = self.mock.start()
        self.addCleanup(self.mock.stop)
        # No context manager: the TLS startup guard belongs to the real launcher.
        self.client = TestClient(worker.app)
        self.addCleanup(self.client.close)

    def test_single_use_removes_file_and_channel_auth_remains_required(self):
        bad = self.client.post("/pair", json={"code": "incorrect-test-code"})
        self.assertEqual(bad.status_code, 401)
        self.assertTrue(self.code_file.exists())
        response = self.client.post("/pair", json={"code": CODE})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.code_file.exists())
        self.assertEqual(response.json()["identity"]["runAs"], "EXAMPLE\\rsatWorker$")
        self.assertEqual(self.client.post("/pair", json={"code": CODE}).status_code, 409)
        self.assertEqual(self.client.get("/admin/ping").status_code, 401)

    def test_expired_code_cannot_issue_channel_credential(self):
        worker._pairing_started -= worker.settings.pairing_ttl_seconds + 1
        response = self.client.post("/pair", json={"code": CODE})
        self.assertEqual(response.status_code, 410)
        self.assertNotIn("worker_token", response.json())

    def test_non_ascii_credentials_are_rejected_not_crashed(self):
        # str comparison with secrets.compare_digest raises TypeError on non-ASCII.
        response = self.client.post("/pair", json={"code": "کد-اشتباه"})
        self.assertEqual(response.status_code, 401)
        latin1 = "Bearer café".encode("latin-1")
        denied = self.client.get("/admin/ping", headers={"Authorization": latin1})
        self.assertEqual(denied.status_code, 401)

    def test_uninitialized_channel_credential_is_never_accepted(self):
        worker.settings.agent_token = "change-me"
        denied = self.client.get("/admin/ping", headers={"Authorization": "Bearer change-me"})
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(self.client.post("/pair", json={"code": CODE}).status_code, 503)

    def test_channel_credential_opens_the_api(self):
        token = worker.settings.agent_token
        with patch("app.routers.admin.run_ps", return_value=IDENTITY):
            response = self.client.get("/admin/ping", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["identity"], IDENTITY)

    def test_anonymous_health_probe_is_cached_and_reports_transport(self):
        first = self.client.get("/health")
        self.assertEqual(first.status_code, 200)
        self.assertIs(first.json()["tls"], False)
        self.assertEqual(first.json()["version"], worker.__version__)
        self.client.get("/health")
        self.client.get("/health")
        self.assertEqual(self.runner.call_count, 1)


if __name__ == "__main__":
    unittest.main()
