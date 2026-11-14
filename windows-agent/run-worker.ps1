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
  Set-Content '.env' $envText -Encoding ASCII
}

if (-not (Test-Path '.venv')) { py -3 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

# The launcher creates the one-time pairing code, prepares the TLS certificate,
# prints the pairing code with the certificate fingerprint and starts the API.
& .\.venv\Scripts\python.exe -m app.launcher
exit $LASTEXITCODE
