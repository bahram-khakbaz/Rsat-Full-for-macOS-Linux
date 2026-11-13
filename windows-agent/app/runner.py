"""Run one fixed PowerShell script with request values supplied as environment data."""

import base64
import html
import json
import os
import re
import subprocess

from fastapi import HTTPException

from .config import settings

# UTF-8 without a byte-order mark in both directions, so non-Latin directory
# names survive the pipe. Setting the console encoding fails harmlessly when
# the process has no console; the stream encoding still applies.
PREAMBLE = (
    "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; "
    "$rsatUtf8=New-Object System.Text.UTF8Encoding $false; "
    "try{[Console]::OutputEncoding=$rsatUtf8}catch{}; $OutputEncoding=$rsatUtf8; "
)
# Worker secrets never belong in a child process environment.
_SCRUBBED = ("AGENT_TOKEN", "PAIRING_CODE", "PAIRING_CODE_FILE")
_TIMEOUT_SECONDS = 45


def _environment(variables: dict | None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.upper() not in _SCRUBBED}
    for key, value in (variables or {}).items():
        if value is None:
            continue  # Absent, not the literal string "None".
        text = str(value)
        if "\x00" in text:
            raise HTTPException(status_code=400, detail="Invalid control character in request")
        env[f"RSAT_{key.upper()}"] = text
    return env


def _error_text(stderr: str, stdout: str) -> str:
    """Return a readable message; PowerShell may serialize errors as CLIXML."""
    text = stderr or stdout or "PowerShell failure"
    if "#< CLIXML" in text:
        parts = re.findall(r'<S S="[Ee]rror">(.*?)</S>', text, flags=re.DOTALL)
        if parts:
            joined = re.sub(
                r"_x([0-9A-Fa-f]{4})_", lambda match: chr(int(match.group(1), 16)), "".join(parts)
            )
            text = html.unescape(joined)
    return text.strip()[:2000]


def _execute(script: str, variables: dict | None) -> str:
    # -EncodedCommand runs the whole script as one unit: a terminating error
    # anywhere fails the call instead of being skipped line by line, which is
    # how PowerShell treats a script piped to "-Command -".
    encoded = base64.b64encode((PREAMBLE + script).encode("utf-16-le")).decode("ascii")
    try:
        proc = subprocess.run(
            [
                settings.powershell_exe,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded,
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=_TIMEOUT_SECONDS,
            env=_environment(variables),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="PowerShell command timed out") from exc
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=_error_text(proc.stderr, proc.stdout))
    raw = (proc.stdout or "").lstrip("﻿").strip()
    if len(raw.encode("utf-8")) > settings.max_output_bytes:
        raise HTTPException(
            status_code=413,
            detail="PowerShell output too large. Select one zone, scope or a narrower search; "
            "no partial result was returned.",
        )
    return raw


def run_ps(script: str, variables: dict | None = None):
    """Run a script that reports one JSON object (or nothing, for plain writes)."""
    raw = _execute(script, variables)
    if not raw:
        return {"ok": True}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": True, "output": raw}


def run_ps_list(script: str, variables: dict | None = None) -> list:
    """Run an inventory script. No output means an empty list, never a fake row."""
    raw = _execute(script, variables)
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502, detail="PowerShell returned an unreadable inventory"
        ) from exc
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
