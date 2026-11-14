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
Get-Content "$env:ProgramData\RSATFull\Worker\tls-fingerprint.txt"
```

Pair in the Mac panel within 15 minutes, comparing the certificate fingerprint
shown there with `tls-fingerprint.txt`. The unattended worker keeps its TLS key
and certificate in the `tls` folder of the state directory, so it has its own
certificate: a worker first paired from an interactive `run-worker.ps1` session
must be paired again after switching to the task (or set `TLS_CERT_FILE` /
`TLS_KEY_FILE`, or one `TLS_STATE_DIR`, for both). The installer ACL-protects the state
directory for SYSTEM, Administrators and the gMSA. Pairing codes are atomically
replaced at each start, never printed by the unattended runner and removed after
successful pairing or normal shutdown. A code left after a crash is unusable
without that running process. Pairing remains single-use. The existing encrypted
worker channel credential is separate from the gMSA password and remains necessary.

The installer refuses to replace an existing task. It does not bypass script
execution policy or create firewall exceptions. Apply signing, network access
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

The script creates `.env` and the internal worker secret on first start, installs
the Python dependencies and then runs `python -m app.launcher`, which:

1. Generates a one-time pairing code in memory.
2. Loads the TLS certificate, creating a self-signed one on first start.
3. Prints the worker URL, pairing code, certificate fingerprint and run-as identity.
4. Starts the worker API over HTTPS on TCP/8765.

Example:

```text
================================================================
 RSAT Full Windows Worker 1.4.0
================================================================
 Worker URL:      https://management-host.example.com:8765
 Pairing code:    ABCD2345WXYZ
                  single use, expires after 15 minutes
 TLS SHA-256:     3f:9a:...:c1
                  self-signed, created by this worker; valid until 2029-11-12.
 Run-as identity: DOMAIN\svc-rsat
================================================================
```

In the macOS/Linux web UI:

1. Open **Settings**.
2. Set the Worker URL, for example `https://management-host.example.com:8765`.
3. Enter the one-time pairing code and compare the certificate fingerprint with
   the one printed by the worker.
4. Click **PAIR WORKER**.
5. Click **TEST WORKER**.
6. Click **DISCOVER DCS FROM AD**.

The pairing code itself is never persisted by the control plane.

## TLS

The worker API carries the channel credential, new account passwords and
directory data, so it is served over HTTPS by default.

- **Self-signed (default).** With no certificate configured the worker creates a
  P-256 key and a self-signed certificate in `worker-state\tls` next to `.env`
  (`<state directory>\tls` for the gMSA task) and reuses them on later starts.
  The directory is limited to the worker account, SYSTEM and Administrators with
  `icacls`; the worker prints a warning if that could not be applied. The
  certificate names the host name, FQDN, `localhost`, local addresses and any
  `TLS_SAN` entries, is valid for three years and is replaced automatically when
  fewer than 30 days remain or the files are damaged. A replacement has a new
  fingerprint, so the worker must be paired again; the banner says when a new
  certificate was created.
- **Your own certificate.** Set `TLS_CERT_FILE` and `TLS_KEY_FILE` (PEM, key
  unencrypted, leaf certificate first) to use a certificate from your PKI.
- **Fingerprint.** The value printed at start and reported by `/health` as
  `tls_fingerprint_sha256` is the SHA-256 of the DER certificate in lowercase
  hex with colons, for example `3f:9a:…:c1`. It is public information; its
  purpose is to let the operator confirm, when pairing, that the control plane
  reached this worker and not something in between.
- **Plain HTTP.** Only with `ALLOW_INSECURE_HTTP=true`, for an isolated lab. The
  worker prints a warning at every start, and starting the API without the
  launcher (for example `uvicorn app.main:app`) is refused unless that setting
  is present. Never use it across a shared network.

## Settings

All settings live in the worker's `.env` (see `.env.example`).

| Setting | Default | Purpose |
| --- | --- | --- |
| `LISTEN_HOST` / `LISTEN_PORT` | `0.0.0.0` / `8765` | Listener address. |
| `TLS_CERT_FILE`, `TLS_KEY_FILE` | empty | Use this certificate instead of the generated one. Set both. |
| `TLS_STATE_DIR` | `worker-state\tls` | Where the generated key and certificate are kept. |
| `TLS_SAN` | empty | Extra DNS names or IP addresses for the generated certificate. |
| `ALLOW_INSECURE_HTTP` | `false` | Serve unencrypted HTTP (lab only). |
| `GPO_BACKUP_ROOT` | `%ProgramData%\RSATFull\GpoBackups` | The only directory tree GPO backups may be written to. |
| `MAX_UNPAGED_RESULTS` | `5000` | Size above which an unpaged inventory fails instead of being cut short. |
| `HEALTH_CACHE_SECONDS` | `60` | How long the anonymous `/health` module probe is cached. |

## Behaviour to know about

- **Non-Latin names.** Account names, group names and distinguished names may
  contain any Unicode letters, digits and combining marks (for example Persian
  names, including the zero-width non-joiner). Quotes, backticks, `$ ; | & < > * ?`
  and control characters are rejected. PowerShell input and output are UTF-8.
- **Search.** User search is a prefix match on `sAMAccountName`, `displayName`
  and `mail`, the same as the direct connector, sent as an LDAP filter that is
  escaped before it reaches PowerShell. Group search is a prefix match on the
  name; computer search matches part of the name or DNS host name.
- **Paging and limits.** With `page_size` (1–100) the user list returns
  `items`, `next_cursor`, `has_more` and `total`; pass `next_cursor` back as
  `cursor` for the next page. A cursor belongs to the search that produced it.
  Pages are offsets into the order Active Directory returns, so a directory
  changed between two requests can shift a row across a page boundary. Without
  `page_size`, and for groups and computers, the full inventory is returned; if
  it exceeds `MAX_UNPAGED_RESULTS` the request fails with HTTP 413 rather than
  returning a partial list. DNS record listings return every record of the
  selected zone and fail explicitly on a read error or oversized result.
- **DNS records.** A, AAAA, CNAME, PTR, NS, MX, SRV and TXT can be listed,
  created, edited and deleted, with the same value formats as the direct
  connector (`MX`: `preference host`; `SRV`: `priority weight port host`; `TXT`:
  one quoted text segment of at most 255 bytes). SOA and other types are listed
  read-only.
- **GPO backups.** The backup path must be an absolute local path inside
  `GPO_BACKUP_ROOT`; network (UNC) and relative paths are refused. `/admin/ping`
  reports the configured directory.
- **Execution.** Each operation runs one fixed script with
  `powershell.exe -EncodedCommand`; request values are passed as `RSAT_*`
  environment variables and never become script text. A PowerShell error fails
  the request.

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

TLS protects the traffic; it does not decide who may connect. The worker API
should still remain on a trusted management network.

For production:

- Restrict TCP/8765 with Windows Firewall so only the control-plane host can connect.
- Keep TLS enabled and compare the certificate fingerprint when pairing.
- Prefer a dedicated management VM.
- Do not expose TCP/8765 to the public Internet.
- Keep the worker under least-privilege delegated rights.

## Re-pairing

If the control plane loses its paired credential:

1. Restart `run-worker.ps1`.
2. A new one-time pairing code will be displayed, with the certificate fingerprint.
3. Open Settings and pair again.

Pair again as well whenever the worker reports a new TLS certificate.

A pairing code expires after 15 minutes and is accepted only once.
