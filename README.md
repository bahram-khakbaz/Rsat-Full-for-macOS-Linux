# RSAT Full for macOS & Linux

A cross-platform administration center for Microsoft Active Directory environments, designed to make the daily ADAC / ADUC / DNS / DHCP / Group Policy workflow usable from macOS and Linux.

The control plane and UI run on macOS/Linux. Microsoft-native RSAT operations run on a dedicated, domain-joined Windows worker through a strict allow-listed API.

> This is not a binary port of MMC. It is a web-native administration layer over supported Microsoft PowerShell/RSAT modules.

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
- A / AAAA / CNAME / PTR inventory
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
- Windows worker URL and encrypted worker token storage
- Demo / production mode switching from UI
- Multiple sites with any number of domain controllers per site
- Automatic domain controller discovery from Active Directory
- Per-DC connectivity checks for DNS, LDAP, Kerberos, SMB, LDAPS and Global Catalog
- Site/DC configuration stored in PostgreSQL and applied without restarting the control plane

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

```text
macOS / Linux
    Browser
       |
       v
 Retro React UI + Nginx :8080
       |
       v
 FastAPI control plane
   |           |
   |           +--> PostgreSQL audit log
   |
   +------------------------------+
                                  |
                                  v
                         Windows Admin Worker
                         domain joined + RSAT
                                  |
          +-----------------------+----------------------+
          |                       |                      |
    Active Directory          DNS / DHCP          Group Policy
```

The Windows worker is modular:

```text
windows-agent/app/
├── main.py
├── common.py
├── models.py
├── runner.py
└── routers/
    ├── ad.py
    ├── domain.py
    ├── network.py
    └── gpo.py
```

See [Architecture](docs/ARCHITECTURE.md).

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

Use a dedicated domain-joined Windows management host. Do not run the worker on a domain controller.

On Windows:

```powershell
cd windows-agent
Copy-Item .env.example .env
notepad .env
.\install-rsat.ps1
.\run-worker.ps1
```

After the first bootstrap, open **Settings** in the web UI. Configure the Windows worker URL/token there, switch from Demo to Production, add your sites and DCs, or use **Discover DCs from AD**. Saved runtime settings take effect without restarting the control plane.

The `.env` values remain bootstrap/fallback values; normal connection and topology management is performed from the UI.

Read [Windows Worker](docs/WINDOWS_WORKER.md), [macOS Deployment](docs/MACOS_DEPLOYMENT.md), and [Security](docs/SECURITY.md) before production use.

## Security model

- No domain credential is stored in the frontend.
- The control plane never exposes a generic PowerShell endpoint.
- Worker calls are bearer-token protected.
- Command values are supplied through process environment variables rather than interpolated into PowerShell source.
- Control-plane permissions separate helpdesk, network, GPO, audit and administrator capabilities.
- Write operations are audited.
- Password values are redacted from audit data.
- The default macOS deployment binds the UI to localhost only.

For production, add organizational OIDC/SSO, TLS, firewall restrictions and a least-privilege delegated worker identity.

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
scripts/          Bootstrap and verification utilities
```

## Verify

```bash
./scripts/verify.sh
```

CI independently tests Python and builds the frontend on every push.

## License

No open-source license has been selected yet. Add a license before redistributing outside your organization.
