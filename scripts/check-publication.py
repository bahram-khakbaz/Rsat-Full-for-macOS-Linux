#!/usr/bin/env python3
"""Reject private artifact paths in the Git index or reachable history.

This is a path guard, not a content/secret scanner. Run Gitleaks as well.
Only Git-tracked paths are examined; private runtime files are never opened.
"""
import argparse
from pathlib import PurePosixPath
import subprocess
import sys


PRIVATE_DIRS = {"outputs", "backups", "downloads", "secrets", "node_modules", ".venv"}
PRIVATE_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".sql", ".dump", ".bak", ".log",
    ".pem", ".key", ".cer", ".crt", ".p12", ".pfx", ".kdbx", ".pcap", ".pcapng",
}


def private_path(name):
    path = PurePosixPath(name.lower())
    if any(part in PRIVATE_DIRS or part.endswith(".app") for part in path.parts):
        return True
    base = path.name
    return (
        (base.startswith(".env") and base != ".env.example")
        or (base.endswith(".env") and base != ".env.example")
        or path.suffix in PRIVATE_SUFFIXES
        or base in {"id_rsa", "id_ed25519", "id_ecdsa", "known_hosts"}
        or base.startswith(("screenshot", "codex-clipboard-"))
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="also check all reachable revisions")
    args = parser.parse_args()
    commands = [["git", "ls-files", "-z"]]
    if args.history:
        commands.append(["git", "log", "--all", "--pretty=format:", "--name-only", "-z"])
    paths = set()
    for command in commands:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE)
        paths.update(p.decode("utf-8", "surrogateescape").strip("\n") for p in result.stdout.split(b"\0") if p.strip(b"\n"))
    rejected = sorted(path for path in paths if private_path(path))
    if rejected:
        print("Publication check failed: private artifact paths are tracked.", file=sys.stderr)
        for path in rejected:
            print(repr(path), file=sys.stderr)
        return 1
    print(f"Publication path check passed ({len(paths)} unique tracked paths).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
