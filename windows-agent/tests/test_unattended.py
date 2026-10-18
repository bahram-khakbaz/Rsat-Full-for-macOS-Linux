import importlib.util
from pathlib import Path
import tempfile
import unittest

source = Path(__file__).resolve().parents[1] / "unattended-worker.py"
spec = importlib.util.spec_from_file_location("unattended_worker", source)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class PairingFileTests(unittest.TestCase):
    def test_pairing_file_is_atomic_private_and_changes_on_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            first, path = worker.write_pairing_file(directory)
            second, same_path = worker.write_pairing_file(directory)
            self.assertNotEqual(first, second)
            self.assertEqual(path, same_path)
            self.assertEqual(path.read_text(), second)
            self.assertGreaterEqual(len(second), 24)
            self.assertEqual(list(Path(directory).iterdir()), [path])
            if __import__("os").name != "nt":
                self.assertEqual(path.stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
