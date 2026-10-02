$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function New-RandomSecret([int]$bytes = 48) {
  $buffer = New-Object byte[] $bytes
  $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
  try {
    $rng.GetBytes($buffer)
  } finally {
    $rng.Dispose()
  }
  return [Convert]::ToBase64String($buffer).TrimEnd('=').Replace('+','A').Replace('/','B')
}

if (-not (Test-Path '.env')) {
  Copy-Item '.env.example' '.env'
}

$envText = Get-Content '.env' -Raw
if ($envText -notmatch '(?m)^AGENT_TOKEN=(.+)$' -or $Matches[1].Trim() -in @('', 'change-me', 'replace-with-a-long-random-token', '__AUTO_GENERATED__')) {
  $secret = New-RandomSecret 48
  if ($envText -match '(?m)^AGENT_TOKEN=.*$') {
    $envText = [regex]::Replace($envText, '(?m)^AGENT_TOKEN=.*$', "AGENT_TOKEN=$secret")
  } else {
    $envText += [Environment]::NewLine + "AGENT_TOKEN=$secret" + [Environment]::NewLine
  }
  Set-Content '.env' $envText -Encoding UTF8
}

$pairingCode = (New-RandomSecret 9).Substring(0,12).ToUpperInvariant()
$env:PAIRING_CODE = $pairingCode

Write-Host ''
Write-Host '============================================================' -ForegroundColor DarkCyan
Write-Host ' RSAT Full Windows Worker' -ForegroundColor Cyan
Write-Host '============================================================' -ForegroundColor DarkCyan
Write-Host " Pairing code: $pairingCode" -ForegroundColor Yellow
Write-Host ' Pairing code expires after 15 minutes and can be used once.' -ForegroundColor DarkGray
Write-Host " Run-as identity: $([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)" -ForegroundColor Gray
Write-Host '============================================================' -ForegroundColor DarkCyan
Write-Host ''

if (-not (Test-Path '.venv')) { py -3 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8765
