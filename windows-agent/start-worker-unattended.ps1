[CmdletBinding()]
param([Parameter(Mandatory)][string]$StateDirectory)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\unattended-worker.py" --state-directory $StateDirectory
exit $LASTEXITCODE
