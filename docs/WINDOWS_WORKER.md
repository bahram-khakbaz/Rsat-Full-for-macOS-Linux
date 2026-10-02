# Windows Admin Worker

Use a dedicated, domain-joined Windows management VM or workstation. Do **not** run the worker on a domain controller.

## Identity model

The macOS/Linux control plane does not store an Active Directory username/password.

The Windows Worker executes RSAT PowerShell under the Windows identity that runs the worker:

- Lab / initial validation: a signed-in domain administrator or delegated admin account.
- Production: a dedicated delegated domain service account or, preferably, a gMSA.
- Do not grant Domain Admin merely for convenience.

Windows Integrated Authentication / Kerberos is therefore used naturally by ActiveDirectory, DNS, DHCP and GroupPolicy cmdlets.

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

## Start and pair

No worker token needs to be created manually.

```powershell
.\run-worker.ps1
```

On first start the script:

1. Creates `.env` if it does not exist.
2. Generates a high-entropy internal worker secret automatically.
3. Generates a one-time pairing code in memory.
4. Prints the current Windows run-as identity.
5. Starts the worker on TCP/8765.

Example:

```text
RSAT Full Windows Worker
Pairing code: ABCD1234WXYZ
Pairing code expires after 15 minutes and can be used once.
Run-as identity: DOMAIN\svc-rsat
```

In the macOS/Linux web UI:

1. Open **Settings**.
2. Set the Worker URL, for example `http://management-host:8765`.
3. Enter the one-time pairing code.
4. Click **PAIR WORKER**.
5. Click **TEST WORKER**.
6. Click **DISCOVER DCS FROM AD**.

The pairing code itself is never persisted by the control plane.

## Verify the Windows identity

Before production use:

```powershell
whoami
Get-ADDomain | Select-Object DNSRoot,PDCEmulator
Get-Module -ListAvailable ActiveDirectory,DnsServer,DhcpServer,GroupPolicy |
  Select-Object Name,Version
```

The account shown by `whoami` is the identity whose delegated permissions will be used by RSAT Full.

## Multi-site environments

The worker queries Active Directory for domain controllers and their AD Sites. The control plane groups discovered DCs by site and stores the topology in PostgreSQL.

For environments with two DCs per site, no manual credential or per-DC login is required. DCs can still be added or corrected manually in Settings.

## Network hardening

The current worker API should remain on a trusted management network.

For production:

- Restrict TCP/8765 with Windows Firewall so only the control-plane host can connect.
- Put TLS in front of the worker if traffic crosses any untrusted or shared segment.
- Prefer a dedicated management VM.
- Do not expose TCP/8765 to the public Internet.
- Keep the worker under least-privilege delegated rights.

## Re-pairing

If the control plane loses its paired credential:

1. Restart `run-worker.ps1`.
2. A new one-time pairing code will be displayed.
3. Open Settings and pair again.

A pairing code expires after 15 minutes and is accepted only once.
