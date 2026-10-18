# RSAT Full for macOS & Linux

A cross-platform administration center for Microsoft Active Directory environments, designed to make the daily ADAC / ADUC / DNS / DHCP / Group Policy workflow usable from macOS and Linux.

The control plane and UI run on macOS/Linux. Direct mode connects to Active Directory using LDAPS and manages DNS/DHCP through encrypted Kerberos RPC, without a Windows intermediary. An optional Windows worker supports additional RSAT and Group Policy operations.

> This is not a binary port of MMC. It is a web-native administration layer using directory protocols and optional Microsoft PowerShell/RSAT modules.

## Interface

The UI uses a self-contained retro systems-console design: dense information, monospace typography, hard borders, explicit state indicators, and keyboard-friendly administration flows. No CDN or external font is required.

Module buttons keep their full labels and wrap into additional rows when the window narrows. Users has wrapping search/actions and pagination, a horizontally scrollable table, and a user inspector that moves below the list in windows up to 1500 pixels wide. Scroll the central workspace to reach user details and account actions in those windows. File Transfer uses aligned local/remote panels, wrapping action bars, dark input controls and bounded tables. At smaller widths the file browsers stack vertically; long file names wrap within their cells. Scroll the central workspace to reach the queue and lower actions in a short window. The desktop layout supports windows at least 800 × 680 pixels; it is not a mobile interface.

Quick links: [macOS app](docs/MACOS_DEPLOYMENT.md) · [Direct AD/DNS/DHCP](docs/direct-mac.md) · [Windows worker](docs/WINDOWS_WORKER.md) · [SFTP guide](docs/FILE_TRANSFER.md) · [Coverage](docs/COVERAGE.md).

## Choose a connection mode

| Area | Direct Mac/Linux | Optional Windows worker |
| --- | --- | --- |
| AD | Directory reads and common LDAP writes; see limitations below | Broader RSAT operations, including user creation and recycle-bin restore |
| DNS | Zone/record inventory; create, edit and delete eight record types | Zone management and worker record operations |
| DHCP | IPv4 scopes, leases and reservations; scope/reservation changes | IPv4 management and statistics |
| Group Policy | Inventory | Management, links, reports, backups and permissions |
| SSH / Linux / SFTP | Independent SSH connection from the backend | No worker needed |

Direct mode needs reachable company DNS/network, trusted LDAPS certificates and the appropriate delegated AD/service rights. It does not implement user creation, protected OU creation, computer-account reset, replication health, recycle-bin restore or full GPO management. DHCP options, exclusions, DHCPv6 and failover management are also not implemented. A successful connection check does not grant write permissions; each destination enforces the account's actual rights.

## Implemented management areas

### Active Directory / ADAC / ADUC

- Domain and forest identity
- FSMO role owners
- Domain controller inventory
- Replication partner health
- Trust inventory
- Sites and subnet inventory
- Default domain password policy
- Fine-grained password policy inventory
- Active Directory Recycle Bin browsing and object restore
- User search and detailed properties
- User creation and attribute editing
- Account unlock, enable, disable and deletion
- Password reset + change-at-next-logon
- Password forms accept 8+ characters; Active Directory still enforces the account's actual password policy
- Move users between OUs
- User group membership view
- Group inventory and creation/deletion
- Group membership add/remove
- Computer inventory/search
- Computer enable/disable/reset/move/delete
- OU inventory/create/delete with accidental deletion handling

### DNS

- Zone inventory
- AD-integrated primary zone creation
- Zone deletion
- Direct record inventory and create/edit/delete: A, AAAA, CNAME, PTR, NS, MX, SRV and TXT
- SOA and unknown record types are read-only
- Browse zones and nested DNS subdomains using folders, a zone tree and breadcrumbs
- New record names are relative to the open folder (`@` targets that folder); edits/deletes retain the original owner name
- Search the open folder and its subfolders, or return to the zone root to search the entire zone
- Zone create/delete requires the Windows worker or optional WinRM connector

### DHCP

- IPv4 scope inventory/statistics
- Scope creation
- Scope activate/deactivate
- Scope deletion
- Lease inventory
- Reservation inventory
- Reservation create/delete

### Group Policy

- GPO inventory
- GPO creation/deletion
- GPO link/unlink
- Link order/enforced state
- User/computer settings status
- GPO backup
- XML report
- Permission/security filtering inventory
- GPO permission updates

### Settings / multi-site topology

- In-panel connection settings; no manual `.env` editing after initial bootstrap
- Windows worker URL + one-time pairing code; no worker secret is typed or managed manually
- The paired worker secret is generated automatically and stored encrypted by the control plane
- Direct mode stores domain credentials encrypted in the local backend; the frontend never receives saved passwords
- In worker mode, AD credentials stay on Windows
- Worker runs under Windows Integrated Authentication using a delegated domain service account or gMSA
- Demo / production mode switching from UI
- Multiple sites with any number of domain controllers per site
- Automatic domain controller discovery from Active Directory
- Per-DC connectivity checks for DNS, LDAP, Kerberos, SMB, LDAPS and Global Catalog
- Site/DC configuration stored in PostgreSQL and applied without restarting the control plane

### SSH and native macOS app

- Separate switch and Linux server inventories, encrypted credentials and verified host keys
- Interactive SSH terminal with per-operator access
- Native RSAT.app launcher starts the existing Colima profile and services, then opens the panel
- Saved database and configuration survive app closure and Mac restarts
- Native file/folder pickers, download save dialog, and standard copy/paste/select-all shortcuts

### File Transfer / SFTP

- Integrated two-pane local selection and remote directory browser; no FileZilla installation needed
- Reuses each operator's saved Linux/switch SSH account and approved host key
- Upload files or selected folder trees, drag/drop files, and download files
- Download a remote directory as ZIP, preserving subfolders and skipping symlinks/special files
- Sequential transfer queue with byte progress, cancellation, explicit retry and overwrite confirmation
- Create folders, rename, change Unix permissions, delete files and empty directories
- Built-in UTF-8 text editor with size/mtime conflict checks before saving
- Temporary uploads commit only after remote size verification; existing files are not replaced by partial uploads
- New uploaded files are private (`0600`); replacements preserve ordinary file permissions
- Admin/network panel roles and the remote SSH account's own permissions govern access

Open **Linux Servers** (or **SSH Switches**), save your SSH account, independently
verify/approve the host key, then choose **FILES / SFTP**. Alternatively open the
**File Transfer** tab, select the saved host and click **CONNECT SFTP**. On the
left, choose files or a folder from the Mac; on the right, browse to the upload
destination. Select local items and click **UPLOAD SELECTED**. Select remote
items and choose **DOWNLOAD / ZIP**. The native Mac app presents its own file
selection and save dialogs.

This connector uses **SFTP over SSH**, not FTP/FTPS. The host must enable an SFTP
subsystem and accept the saved password login. The current per-file limit is
512 MiB; UTF-8 editing is limited to 512 KiB. Folder ZIPs allow up to 512 MiB of
uncompressed file data, 10,000 entries and 32 directory levels. Non-empty folder
deletion is deliberately non-recursive. Transfers are not resumed after closing
the page/app. See [File Transfer](docs/FILE_TRANSFER.md) for details and limits.

### VLAN / manual IP allocation

Below **Linux Servers**, maintain per-operator IPv4 subnet inventories with free,
used, reserved and unknown counts. Select a VLAN, leave **ONLY FREE IPs** checked,
and check an address to mark it used; it disappears from the free list after the
save succeeds. Uncheck the filter to view all addresses and release an allocation
or set its status explicitly. Changes are saved immediately in the local database
and audited. Reserved addresses have a disabled Used checkbox; change their status
explicitly with the allocation selector if needed.

Network and broadcast addresses are excluded from usable totals. Gateways must be
reserved explicitly. New subnets default to unknown status, overlapping subnets in
the same operator's inventory are rejected, and stale updates from another window
are blocked until refresh. Supported subnet sizes are /20 through /30. This is a
manual allocation register: it does not scan devices, reserve DHCP leases, change
VLANs on switches or prove that a free-labelled address is safe to assign.

Real inventories remain in the local database, never in demo fixtures or GitHub.

### Platform

- FastAPI control plane
- PostgreSQL audit trail
- Role-based authorization
- Expiring JWT sessions
- Dedicated Windows RSAT worker
- No arbitrary PowerShell execution endpoint
- Docker Compose deployment
- macOS bootstrap
- Demo mode
- GitHub Actions CI

## Architecture

The browser or native macOS app connects to Nginx and FastAPI, with PostgreSQL holding configuration and audit data. Direct mode connects to AD over validated LDAPS, DNS through Samba RPC, DHCP through Impacket RPC, and switches/Linux hosts over SSH or SFTP. Optional worker mode uses the allow-listed Windows management API.

See [Direct Mac connection](docs/direct-mac.md) for supported operations and limitations. The lists above include worker capabilities; direct mode has a narrower scope.

## Start on macOS

Prerequisite: Docker Desktop, Rancher Desktop, or Colima with Docker Compose.

```bash
git clone https://github.com/bahram-khakbaz/Rsat-Full-for-macOS-Linux.git
cd Rsat-Full-for-macOS-Linux
chmod +x scripts/*.sh
./scripts/macos-bootstrap.sh
```

Open:

```text
http://localhost:8080
```

The bootstrap script creates local secrets and prints the generated administrator password once.

## Demo mode

The initial configuration uses:

```env
DEMO_MODE=true
```

The complete UI can therefore be explored without a domain controller or Windows worker.

## Connect a real AD environment

For direct access, open **Settings**, choose Direct Mac Connection, enter your domain and UPN, and save the password locally. Supply a trusted corporate CA or explicitly approve a DC certificate fingerprint after independent verification. Disable Demo mode and select enabled DCs. AD requests connect automatically; no per-DC pairing is required. Configure DNS and the actual authorized DHCP service host in the service settings. Company DNS and network/VPN access must be available from the containers.

Read [Direct Mac connection](docs/direct-mac.md) for permissions, protocol requirements and limitations, and [macOS deployment](docs/MACOS_DEPLOYMENT.md) to build the one-click app.

For additional Windows RSAT/GPO features, start `windows-agent/run-worker.ps1` on a dedicated domain-joined management host, pair its URL and one-time code in Settings, and use a delegated service account or gMSA. See [Windows Worker](docs/WINDOWS_WORKER.md).

## Security model

Optional [Vault Agent delivery](docs/VAULT_AGENT.md) keeps AD/SSH password values
out of the application database; RSAT stores operator-scoped references and reads
fresh, protected deliveries on use. The app does not receive a Vault token. Local
encrypted storage remains the default and no existing credentials are migrated.

The [gMSA startup-task installer](docs/WINDOWS_WORKER.md#gmsa-unattended-startup)
provides an opt-in unattended Windows Worker path without an operator-entered AD
password. It requires a pre-provisioned, host-authorized gMSA and delegated rights.
Automated task-definition checks do not replace validation on a real domain host.

The repository contains synthetic demo/test data only. Real domain settings,
host inventories, credentials and audit events belong in the private local
environment/database, never in source control. See the
[publication checklist](docs/SECURITY.md#publication-hygiene) before sharing a
fork, release, screenshot or diagnostic export.

- No domain credential is stored in the frontend.
- The control plane never exposes a generic PowerShell endpoint.
- Worker calls are protected by an internal high-entropy credential created automatically on Windows.
- The operator never manages that credential directly; a one-time pairing code exchanges it with the control plane.
- Pairing codes expire after 15 minutes and are single-use.
- Direct-mode credentials are encrypted locally and never returned to the web UI. Keep JWT_SECRET stable and protect the environment file and database backups.
- LDAPS trust is verified before binding; RPC requires Kerberos and packet privacy; SSH verifies approved host keys before sending passwords.
- The Windows worker uses the security token of its own domain account (preferably a delegated service account/gMSA).
- Command values are supplied through process environment variables rather than interpolated into PowerShell source.
- Control-plane permissions separate helpdesk, network, GPO, audit and administrator capabilities.
- Write operations are audited.
- Password values are redacted from audit data.
- The default macOS deployment binds the UI to localhost only.

For shared production deployments, add organizational OIDC/SSO, TLS and firewall restrictions. Delegate only the directory/service rights needed by the chosen mode.

## Scope boundary

This project targets the ADAC / ADUC / DNS / DHCP / GPMC workflows administrators use most often.

Specialized RSAT consoles such as AD CS, DFS, Failover Clustering, NPS, WSUS, Hyper-V Manager, Storage Migration Service and every possible MMC extension are separate products/domains and are not claimed as implemented here.

See [Coverage](docs/COVERAGE.md).

## Repository structure

```text
backend/          FastAPI control plane, RBAC and audit
frontend/         Cross-platform retro administration UI
windows-agent/    Windows-only allow-listed RSAT execution layer
docs/             Architecture, security and deployment docs
scripts/          Bootstrap, macOS app builder and verification utilities
macos/            Native app source, startup helper and isolated tests
```

## Verify

```bash
./scripts/verify.sh
```

CI independently tests Python and builds the frontend on every push.

For the individual checks used by CI:

```bash
pip install -r backend/requirements.txt
PYTHONPATH=backend pytest -q backend/tests
python3 macos/tests/test_launcher.py
cd frontend
npm ci --no-audit --no-fund
node --test src/api-errors.test.mjs src/file-transfer.test.mjs src/dns-browser.test.mjs
npm run build
```

Backend RPC tests additionally require the system Kerberos and Samba dependencies used in the backend Dockerfile and CI workflow. Use Python 3.13 and Node.js 22 as in CI. If host dependencies were installed on another operating system, use a clean `npm ci` or build with `docker compose build web`; do not reuse Linux `node_modules` on macOS.

UI acceptance uses disposable loopback SFTP fixtures, including upload and long file names, rather than production server writes. Automated mocks and local fixtures do not establish compatibility with every organization's AD, DHCP or SSH configuration.

## Update an existing installation

Back up the database and protect the existing `.env` first. Keep `JWT_SECRET` unchanged: saved encrypted credentials depend on it. From the same checkout and Compose project used for installation:

```bash
git pull --ff-only
docker compose up -d --build --wait
```

Reload the panel after the build (⌘R in RSAT.app). UI-only changes do not require rebuilding the native launcher. If native macOS source changes, follow the app build/install instructions in [macOS deployment](docs/MACOS_DEPLOYMENT.md). Do not remove the database volume while updating.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Old controls or layout after an update | Confirm the web image was rebuilt and the web container recreated, then reload the panel. |
| DC online but directory reads fail | Port reachability is not an authenticated LDAP read. Check direct credentials, LDAPS trust, DNS and the requested capability. |
| DNS/DHCP connection works but a change fails | Verify delegated rights and the selected service host; preserve the displayed partial-failure details before retrying. |
| SSH/SFTP cannot connect | Save the account/password, approve an independently verified host key, and check network access. SFTP additionally needs a server SFTP subsystem. |
| File transfer denied | Check the remote account's read/write permissions and the panel role. A remote permission denial does not invalidate the panel login. |
| Some operations are disabled | Check the connection-mode coverage and assigned panel role; unsupported direct-mode operations require the optional worker. |

## Suggested next additions (not implemented)

1. **SSH keys and SSH-agent authentication**, with per-host identity selection, to complement password authentication.
2. **Resumable transfers and directory synchronization**, with previews, conflict handling and independent remote checksum verification.
3. **Linux operations dashboard** for service status, resource usage and searchable logs, followed by explicitly authorized service actions.
4. **Bulk AD/DNS changes with a dry-run preview**, CSV validation and an audit-linked change report before applying writes.
5. **Backup/restore and access management**: verified configuration/database recovery, organizational SSO/MFA and more granular operator permissions.

These are a roadmap, not current guarantees. Server actions and bulk changes should preserve the existing host-key checks, delegated rights and audit trail.

## License

No open-source license has been selected yet. Add a license before redistributing outside your organization.
