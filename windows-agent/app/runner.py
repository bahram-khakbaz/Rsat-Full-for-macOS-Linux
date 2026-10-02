import json
import os
import subprocess
from fastapi import HTTPException
from .config import settings

def run_ps(script: str, variables: dict[str, str] | None = None):
    env = os.environ.copy()
    for key, value in (variables or {}).items():
        env[f"RSAT_{key.upper()}"] = str(value)
    wrapped = "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; " + script
    try:
        proc = subprocess.run(
            [settings.powershell_exe, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", "-"],
            input=wrapped, capture_output=True, text=True, timeout=45, env=env, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="PowerShell command timed out") from exc
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=(proc.stderr or proc.stdout or "PowerShell failure")[:2000])
    raw = (proc.stdout or "").strip()
    if len(raw.encode()) > settings.max_output_bytes:
        raise HTTPException(status_code=413, detail="PowerShell output too large")
    if not raw:
        return {"ok": True}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": True, "output": raw}
