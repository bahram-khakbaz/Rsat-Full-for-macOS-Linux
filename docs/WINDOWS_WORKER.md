# Windows Admin Worker

Use a dedicated, domain-joined Windows management VM or workstation. Do not run the worker on a domain controller.

## Install RSAT

Open elevated PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install-rsat.ps1
```

Required modules:

- ActiveDirectory
- DnsServer
- DhcpServer
- GroupPolicy

## Configure the worker

Copy `.env.example` to `.env` and set a long random `AGENT_TOKEN`.

```powershell
Copy-Item .env.example .env
notepad .env
```

## Start

```powershell
.\run-worker.ps1
```

Health endpoint:

```powershell
Invoke-RestMethod http://localhost:8765/health
```

## Production hardening

- Run under a dedicated service account with only delegated permissions required by your workflows.
- Prefer JEA as the environment matures.
- Restrict TCP/8765 with Windows Firewall to the control-plane host only.
- Terminate TLS in front of the worker if traffic crosses an untrusted segment.
- Never grant Domain Admin merely for convenience.
