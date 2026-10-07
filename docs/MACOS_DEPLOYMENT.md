# macOS deployment

## Initial installation

Install Git and Docker Compose (Docker Desktop, Rancher Desktop or Colima). Clone the repository, run `./scripts/macos-bootstrap.sh`, and open http://localhost:8080. The bootstrap generates `.env` with private secrets and an administrator password, builds the services and binds the web interface to localhost. Keep the repository, `.env` and PostgreSQL volume.

Configure the direct domain connection in Settings as described in [Direct Mac connection](direct-mac.md). A reachable company network/VPN, company DNS and trusted LDAPS certificate are required. Optional Windows worker setup is described in [Windows Worker](WINDOWS_WORKER.md); do not manually copy worker secrets.

## Native one-click app

The native launcher requires macOS 13+, Xcode Command Line Tools, Docker CLI and the existing default Colima profile. Complete the initial Compose build using the Colima context before building the app; its startup helper never downloads or rebuilds images.

```bash
python3 scripts/build-macos-app.py
open .macos-build
```

Move the generated **RSAT.app** to Applications using Finder, open it, then choose **Options → Keep in Dock**. The builder embeds the local clone location into the generated app only. Rebuild the app if the repository moves. Generated apps, logs and local configuration are excluded from Git.

Opening RSAT starts the existing Colima profile when necessary, starts the same Compose project without removing data, checks service health and loads the panel in a native window. Closing the window leaves the services running. After a Mac restart, open the app again. Startup errors offer Retry and a private log in `~/Library/Logs/RSAT/`. The app does not bypass panel login or start automatically at OS login. An expired session requires login again. Company network/VPN access is still needed for live management.

## Panel password

The local panel account is separate from the AD and SSH accounts. To change its password, edit `ADMIN_PASSWORD` in the private `.env` file and reopen RSAT to apply the environment, or run `docker --context colima compose up -d`. Keep **JWT_SECRET unchanged**: it protects saved domain and switch credentials. Do not commit `.env` or password files.

Back up PostgreSQL together with the protected environment file. For shared access, add HTTPS and organizational SSO before exposing the service beyond localhost.

## Verification

`python3 macos/tests/test_launcher.py` checks cold/warm startup and error handling with stub commands, without stopping the real VM or changing infrastructure. Building the app verifies its native compilation and signature. These checks do not simulate a physical Mac power cycle.
