# RSAT Full for macOS & Linux

A cross-platform web administration center for Microsoft Active Directory environments. The UI and control plane run on macOS or Linux; privileged RSAT operations execute on a dedicated domain-joined Windows worker through an allow-listed API.

> This project does not attempt to run Microsoft MMC binaries on macOS. It provides a modern web control plane for common RSAT workflows while keeping Windows-native operations on Windows.

## What is included

- Modern React administration UI
- FastAPI control plane
- Local authentication for standalone deployment
- Role-based access control foundation
- PostgreSQL audit trail
- Active Directory users, groups, computers and OUs
- Unlock / enable / disable / password reset workflows
- Windows DNS inventory and record creation API
- Windows DHCP scope statistics and reservation API
- Group Policy inventory and GPO creation API
- Windows RSAT worker with no arbitrary PowerShell endpoint
- Docker Compose deployment for macOS and Linux
- Demo mode so the application can be explored without an AD environment
- GitHub Actions CI

## Architecture

```text
macOS / Linux
    Browser
       |
       v
 React + Nginx :8080
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
                 +----------------+----------------+
                 |                |                |
           Active Directory      DNS/DHCP         GPO
```

See [Architecture](docs/ARCHITECTURE.md) for the trust boundaries and design rationale.

## Start on a Mac

```bash
git clone https://github.com/bahram-khakbaz/Rsat-Full-for-macOS-Linux.git
cd Rsat-Full-for-macOS-Linux
./scripts/macos-bootstrap.sh
```

Then open:

```text
http://localhost:8080
```

The bootstrap script generates the local secrets and prints the generated admin password once.

## Demo mode

The generated configuration starts with:

```env
DEMO_MODE=true
```

This provides sample AD, DNS, DHCP and GPO data without contacting any domain controller.

## Connect a real Windows / AD environment

1. Prepare a dedicated domain-joined Windows management host.
2. Copy the `windows-agent` directory to it.
3. Install the RSAT modules with `windows-agent/install-rsat.ps1`.
4. Configure `windows-agent/.env` with a strong worker token.
5. Start the worker with `windows-agent/run-worker.ps1`.
6. On the Mac edit `.env` and set:

```env
DEMO_MODE=false
WORKER_URL=http://your-management-host:8765
WORKER_TOKEN=<same-worker-token>
```

7. Restart:

```bash
docker compose up -d --build
```

Full instructions: [Windows Worker](docs/WINDOWS_WORKER.md) and [macOS Deployment](docs/MACOS_DEPLOYMENT.md).

## Security

The repository contains no real domain data or credentials. The Windows worker only exposes explicit administration actions and does not offer arbitrary PowerShell execution. Production deployments should use organizational SSO, TLS, a least-privilege service identity, firewall restrictions, and centralized audit shipping.

Read [Security](docs/SECURITY.md) before production use.

## Current coverage and boundaries

The project covers common day-to-day RSAT administration, but a complete reimplementation of every Microsoft MMC snap-in is a much larger product. Advanced Group Policy editing and specialized consoles such as AD CS, DFS, Failover Clustering, and forest/schema administration remain delegated to native Windows tools in this release.

See [Coverage](docs/COVERAGE.md).

## Repository structure

```text
backend/          FastAPI control plane and audit/RBAC
frontend/         React web UI
windows-agent/    Windows-only allow-listed RSAT worker
docs/             Architecture, security and deployment docs
scripts/          Bootstrap and verification utilities
```

## Verify the source tree

```bash
./scripts/verify.sh
```

## License

No open-source license has been selected yet. Add a license before redistributing the project outside your organization.
