# macOS deployment

## Prerequisites

- macOS on Intel or Apple Silicon
- Docker Desktop, Rancher Desktop, or Colima with Docker Compose support
- Git
- OpenSSL

## Local demo

```bash
git clone https://github.com/bahram-khakbaz/Rsat-Full-for-macOS-Linux.git
cd Rsat-Full-for-macOS-Linux
chmod +x scripts/*.sh
./scripts/macos-bootstrap.sh
```

Open `http://localhost:8080`.

The bootstrap script creates `.env`, generates local secrets, builds all containers, and binds the web interface to `127.0.0.1` only.

## Connect to a real Active Directory environment

Edit `.env`:

```env
DEMO_MODE=false
WORKER_URL=http://your-windows-management-host:8765
WORKER_TOKEN=<same token configured on the Windows worker>
```

Then restart:

```bash
docker compose up -d --build
```

For a shared deployment, use HTTPS and organizational SSO before exposing the service beyond localhost.
