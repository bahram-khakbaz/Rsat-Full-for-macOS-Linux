# RSAT Full for macOS & Linux

A cross-platform administration center for Microsoft Active Directory environments, designed to make the daily ADAC / ADUC / DNS / DHCP / Group Policy workflow usable from macOS and Linux.

The control plane and UI run on macOS/Linux. Direct mode connects to Active Directory using LDAPS and manages DNS/DHCP through encrypted Kerberos RPC, without a Windows intermediary. An optional Windows worker supports additional RSAT and Group Policy operations.

> This is not a binary port of MMC. It is a web-native administration layer using directory protocols and optional Microsoft PowerShell/RSAT modules.

## Interface

The UI uses a self-contained retro systems-console design: dense information, monospace typography, hard borders, explicit state indicators, and keyboard-friendly administration flows. No CDN or external font is required.

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
- Zone create/delete requires the Windows worker or optional WinRM connector
- Record creation
- Record deletion

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

The browser or native macOS app connects to Nginx and FastAPI, with PostgreSQL holding configuration and audit data. Direct mode connects to AD over validated LDAPS, DNS through Samba RPC, DHCP through Impacket RPC, and switches over SSH. Optional worker mode uses the allow-listed Windows management API.

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

## License

No open-source license has been selected yet. Add a license before redistributing outside your organization.
