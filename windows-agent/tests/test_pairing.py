from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app import main as worker


class UnattendedPairingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.code_file = Path(self.directory.name) / "pairing-code.txt"
        self.code_file.write_text("test-only-pairing-code")
        worker._pairing_started = time.monotonic()
        worker._pairing_used = False
        worker._pairing_attempts = 0
        worker.settings.pairing_code = "test-only-pairing-code"
        worker.settings.agent_token = "test-only-channel-credential" * 2
        worker.settings.pairing_code_file = str(self.code_file)
        self.mock = patch.object(worker, "run_ps", return_value={"runAs":"EXAMPLE\\rsatWorker$", "computer":"TEST-HOST", "domain":"example.com"})
        self.mock.start(); self.addCleanup(self.mock.stop)
        self.client = TestClient(worker.app)
        self.addCleanup(self.client.close)

    def test_single_use_removes_file_and_channel_auth_remains_required(self):
        bad = self.client.post("/pair", json={"code":"incorrect-test-code"})
        self.assertEqual(bad.status_code, 401)
        self.assertTrue(self.code_file.exists())
        response = self.client.post("/pair", json={"code":"test-only-pairing-code"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.code_file.exists())
        self.assertEqual(response.json()["identity"]["runAs"], "EXAMPLE\\rsatWorker$")
        self.assertEqual(self.client.post("/pair", json={"code":"test-only-pairing-code"}).status_code, 409)
        self.assertEqual(self.client.get("/admin/ping").status_code, 401)

    def test_expired_code_cannot_issue_channel_credential(self):
        worker._pairing_started -= worker.settings.pairing_ttl_seconds + 1
        response = self.client.post("/pair", json={"code":"test-only-pairing-code"})
        self.assertEqual(response.status_code, 410)
        self.assertNotIn("worker_token", response.json())


if __name__ == "__main__":
    unittest.main()
