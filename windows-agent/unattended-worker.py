"""Worker entrypoint for an administrator-provisioned gMSA startup task."""
import argparse
import os
from pathlib import Path
import secrets
import tempfile


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
    # Import config only after chdir so the protected deployment .env is used.
    from app.config import settings
    if settings.agent_token in ("", "change-me", "__AUTO_GENERATED__") or len(settings.agent_token) < 32:
        raise RuntimeError("Initialize the worker's channel credential before unattended startup")
    code, target = write_pairing_file(args.state_directory)
    settings.pairing_code = code
    settings.pairing_code_file = str(target)
    try:
        import uvicorn
        from app.main import app
        uvicorn.run(app, host=settings.listen_host, port=settings.listen_port)
    finally:
        target.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
