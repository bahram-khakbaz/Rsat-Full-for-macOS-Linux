"""Worker entrypoint for an administrator-provisioned gMSA startup task."""

import argparse
import os
import secrets
import tempfile
from pathlib import Path


def write_pairing_file(directory):
    # On Windows the installer protects this directory with a dedicated ACL.
    target = Path(directory) / "pairing-code.txt"
    code = secrets.token_urlsafe(18)
    fd, temporary = tempfile.mkstemp(prefix="pairing-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(code)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return code, target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-directory", required=True)
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parent)
    # Import only after chdir so the protected deployment .env is used.
    from app.config import settings
    from app.launcher import serve

    if not settings.token_initialized:
        raise RuntimeError("Initialize the worker's channel credential before unattended startup")
    code, target = write_pairing_file(args.state_directory)
    try:
        # The pairing code is never printed here; it is read from the protected file.
        serve(
            pairing_code=code,
            pairing_code_file=str(target),
            state_directory=Path(args.state_directory),
            show_pairing_code=False,
        )
    finally:
        target.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
