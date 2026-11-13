"""PowerShell invocation contract and the GPO backup directory boundary."""

import base64
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app import runner
from app.routers import gpo


def completed(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def decoded_script(call):
    arguments = call.args[0]
    return base64.b64decode(arguments[arguments.index("-EncodedCommand") + 1]).decode("utf-16-le")


def test_script_runs_as_one_utf8_unit_with_values_only_in_environment(monkeypatch):
    monkeypatch.setenv("AGENT_TOKEN", "must-not-leak")
    monkeypatch.setenv("PAIRING_CODE", "must-not-leak")
    value = "رضا'; Remove-Item C:\\ -Recurse; #"
    with patch.object(subprocess, "run", return_value=completed('{"name":"رضا"}')) as run:
        assert runner.run_ps("Get-Thing $env:RSAT_NAME", {"name": value, "order": None}) == {
            "name": "رضا"
        }
    script = decoded_script(run.call_args)
    assert script.endswith("Get-Thing $env:RSAT_NAME") and value not in script
    assert "$ErrorActionPreference='Stop'" in script and "UTF8Encoding" in script
    options = run.call_args.kwargs
    assert options["encoding"] == "utf-8" and options["stdin"] is subprocess.DEVNULL
    environment = options["env"]
    assert environment["RSAT_NAME"] == value
    assert "RSAT_ORDER" not in environment  # None is absent, not the text "None".
    assert "AGENT_TOKEN" not in environment and "PAIRING_CODE" not in environment


def test_empty_inventory_is_an_empty_list_and_single_object_is_wrapped():
    with patch.object(subprocess, "run", return_value=completed("")):
        assert runner.run_ps_list("x") == []
        assert runner.run_ps("x") == {"ok": True}
    with patch.object(subprocess, "run", return_value=completed('\ufeff{"name":"one"}\r\n')):
        assert runner.run_ps_list("x") == [{"name": "one"}]
    with patch.object(subprocess, "run", return_value=completed("not json")):
        with pytest.raises(HTTPException) as error:
            runner.run_ps_list("x")
        assert error.value.status_code == 502


def test_failures_timeouts_and_oversized_output_are_explicit(monkeypatch):
    clixml = (
        '#< CLIXML\r\n<Objs Version="1.1.0.1"><S S="Error">Access is denied_x000D__x000A_</S>'
        '<S S="Error">At line:1 &lt;here&gt;_x000D__x000A_</S></Objs>'
    )
    with patch.object(subprocess, "run", return_value=completed(stderr=clixml, returncode=1)):
        with pytest.raises(HTTPException) as error:
            runner.run_ps("x")
    assert error.value.status_code == 500
    assert error.value.detail.startswith("Access is denied") and "<here>" in error.value.detail
    assert "CLIXML" not in error.value.detail

    timeout = subprocess.TimeoutExpired(cmd="powershell", timeout=45)
    with patch.object(subprocess, "run", side_effect=timeout):
        with pytest.raises(HTTPException) as error:
            runner.run_ps("x")
    assert error.value.status_code == 504

    monkeypatch.setattr(runner.settings, "max_output_bytes", 8)
    with patch.object(subprocess, "run", return_value=completed('{"too":"large"}')):
        with pytest.raises(HTTPException) as error:
            runner.run_ps_list("x")
    assert error.value.status_code == 413

    with pytest.raises(HTTPException) as error:
        runner.run_ps("x", {"name": "nul\x00byte"})
    assert error.value.status_code == 400


def test_gpo_backup_stays_inside_the_configured_root(monkeypatch):
    monkeypatch.setattr(gpo.settings, "gpo_backup_root", r"D:\GpoBackups")
    monkeypatch.setattr(gpo, "FOLLOW_LINKS", False)  # Pure path rules; no junction lookup.
    assert gpo.backup_directory(r"D:\GpoBackups") == r"D:\GpoBackups"
    assert gpo.backup_directory(r"d:\gpobackups\2026\Baseline") == r"d:\gpobackups\2026\Baseline"
    assert gpo.backup_directory("D:/GpoBackups/weekly") == r"D:\GpoBackups\weekly"
    for path in (
        r"D:\GpoBackups\..\Windows",
        r"D:\GpoBackupsEvil",
        r"C:\GpoBackups",
        r"\\fileserver\share\GpoBackups",
        r"\\?\D:\GpoBackups",
        r"GpoBackups\relative",
        r"D:relative",
        r"D:\GpoBackups\name:stream",
        r"D:\GpoBackups\wild*",
    ):
        with pytest.raises(HTTPException) as error:
            gpo.backup_directory(path)
        assert error.value.status_code == 422, path


def test_gpo_backup_passes_only_the_validated_directory(monkeypatch):
    from app.models import BackupBody

    monkeypatch.setattr(gpo.settings, "gpo_backup_root", r"D:\GpoBackups")
    monkeypatch.setattr(gpo, "FOLLOW_LINKS", False)
    identifier = "0f8fad5b-d9cb-469f-a165-70867728950e"
    with patch("app.routers.gpo.run_ps", return_value={"ok": True}) as runner_mock:
        gpo.gpo_backup(identifier, BackupBody(path=r"D:\GpoBackups\a\..\b"))
        assert runner_mock.call_args.args[1] == {"id": identifier, "path": r"D:\GpoBackups\b"}
        with pytest.raises(HTTPException):
            gpo.gpo_backup(identifier, BackupBody(path=r"C:\Windows\Temp"))
        assert runner_mock.call_count == 1
