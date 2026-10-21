from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.models import AccountOptions
from app.routers.ad import account_options


def test_account_options_forward_only_supplied_fields():
    with patch('app.routers.ad.run_ps', return_value={'ok': True}) as runner:
        assert account_options('tester', AccountOptions(password_never_expires=False)) == {'ok': True}
        script, payload = runner.call_args.args
        assert payload == {'id': 'tester', 'password_never_expires': False}
        assert '[bool]::Parse' in script
        assert 'Set-ADUser -Identity $id @p' in script
        assert script.index('if($never -and $must)') < script.index('Set-ADUser -Identity $id @p')


def test_expiration_is_timezone_aware_and_can_be_cleared():
    with patch('app.routers.ad.run_ps', return_value={'ok': True}) as runner:
        account_options('tester', AccountOptions(account_never_expires=True))
        assert runner.call_args.args[1]['account_never_expires'] is True
        assert '$p.AccountExpirationDate=$null' in runner.call_args.args[0]
    with pytest.raises(ValidationError):
        AccountOptions(account_expires='2030-05-01T12:00:00')


def test_invalid_or_conflicting_options_are_rejected():
    for body in ({'password_never_expires': True, 'change_password_at_logon': True},
                 {'account_never_expires': False}, {'enabled': True},
                 {'logon_workstations': 'PC01;Write-Output anything'}):
        with pytest.raises(ValidationError):
            AccountOptions(**body)


def test_powershell_account_options_script_parses_when_shell_is_available():
    import shutil
    import subprocess
    shell = shutil.which('pwsh') or shutil.which('powershell')
    if not shell:
        pytest.skip('PowerShell syntax validation runs on Windows CI')
    with patch('app.routers.ad.run_ps', return_value={'ok': True}) as runner:
        account_options('tester', AccountOptions(account_never_expires=True))
        script = runner.call_args.args[0]
    parser = '$tokens=$null;$errors=$null;[void][System.Management.Automation.Language.Parser]::ParseInput([Console]::In.ReadToEnd(),[ref]$tokens,[ref]$errors);if($errors.Count){$errors|Out-String|Write-Error;exit 1}'
    result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-Command', parser], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
