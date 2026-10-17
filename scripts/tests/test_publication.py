import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "check-publication.py"
spec = importlib.util.spec_from_file_location("publication_guard", SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class PublicationTests(unittest.TestCase):
    def test_examples_and_source_are_allowed(self):
        for name in [".env.example", "windows-agent/.env.example", "backend/app/config.py", "docs/SECURITY.md"]:
            self.assertFalse(guard.private_path(name), name)

    def test_runtime_artifacts_are_rejected(self):
        for name in [".env", ".env.production", "server.env", "data/backup.sql", "data/panel.sqlite3", "secrets/token.txt", "outputs/report.json", "RSAT.app/Contents/Info.plist", "id_ed25519", "Screenshot 1.png", "certs/client.pfx"]:
            self.assertTrue(guard.private_path(name), name)

    def test_index_and_deleted_history_are_checked(self):
        with tempfile.TemporaryDirectory(prefix="rsat-publication-test-") as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)

            def check(*args):
                return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=root, capture_output=True)

            git("init")
            git("config", "user.name", "Synthetic Test")
            git("config", "user.email", "test@example.com")
            (root / ".env.example").write_text("PLACEHOLDER=example\n")
            git("add", ".env.example")
            self.assertEqual(check().returncode, 0)
            git("commit", "-m", "Synthetic example")
            (root / ".env").write_text("PLACEHOLDER=example\n")
            git("add", ".env")
            self.assertEqual(check().returncode, 1)
            git("commit", "-m", "Synthetic forbidden artifact")
            git("rm", ".env")
            git("commit", "-m", "Remove synthetic artifact")
            self.assertEqual(check().returncode, 0)
            self.assertEqual(check("--history").returncode, 1)


if __name__ == "__main__":
    unittest.main()
