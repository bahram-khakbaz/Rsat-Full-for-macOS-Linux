# Windows Admin Worker

## gMSA unattended startup

`install-gmsa-task.ps1` registers a Task Scheduler startup task under an existing
gMSA. It is a startup task, not a Windows Service wrapper. It does not create an
AD account, change KDS/domain settings, grant AD rights or ask for a gMSA password.
Windows manages that account's password; the worker inherits its security token.

Prerequisites:

- A dedicated domain-joined management host, not a DC, with RSAT modules and a
  machine-wide Python installation usable by the gMSA.
- An administrator-provisioned gMSA, the host authorized to retrieve its password,
  `Install-ADServiceAccount` completed on the host, and `Test-ADServiceAccount`
  returning true. Use the same domain as the management host.
- Delegate only necessary AD/DNS/DHCP/GPO rights. Do not make it a Domain Admin.
  The account needs the applicable batch-logon right; organizational policy must
  not deny it. The task requests Limited run level.
- An administrator-owned deployment directory and `.env`, readable by the gMSA
  but not writable by other operators. Check ACLs on the entire code/venv tree
  and Python installation; the task does not harden that deployment tree for you.
- Initialize `.venv`, dependencies and a strong channel credential with the normal
  setup first. Stop the foreground worker before starting the task on its port.

From an elevated PowerShell in the worker deployment directory:

```powershell
.\install-gmsa-task.ps1 -Account 'EXAMPLE\rsatWorker$' -WhatIf
.\install-gmsa-task.ps1 -Account 'EXAMPLE\rsatWorker$'
Start-ScheduledTask -TaskName 'RSAT-Full-Worker'
Get-Content "$env:ProgramData\RSATFull\Worker\pairing-code.txt"
```

Pair in the Mac panel within 15 minutes. The installer ACL-protects the state
directory for SYSTEM, Administrators and the gMSA. Pairing codes are atomically
replaced at each start, never printed by the unattended runner and removed after
successful pairing or normal shutdown. A code left after a crash is unusable
without that running process. Pairing remains single-use. The existing encrypted
worker channel credential is separate from the gMSA password and remains necessary.

The installer refuses to replace an existing task. It does not bypass script
execution policy or create firewall exceptions. Apply signing, TLS/network access
controls and deployment ACLs according to your environment before starting it.
Use `Stop-ScheduledTask` to stop and `Unregister-ScheduledTask` to remove the task;
neither removes the AD account or local `.env`. Review protected files separately.

CI validates PowerShell syntax, creates an unregistered synthetic task definition
and checks pairing-file lifecycle. Actual gMSA logon, Kerberos delegation and AD
operations still require an authorized Windows domain-host acceptance test.

References: [Microsoft gMSA management](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-managed-service-accounts/group-managed-service-accounts/manage-group-managed-service-accounts),
[Task Scheduler principals](https://learn.microsoft.com/en-us/powershell/module/scheduledtasks/new-scheduledtaskprincipal).

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
