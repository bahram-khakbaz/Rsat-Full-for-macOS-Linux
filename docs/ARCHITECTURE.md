# Architecture

The browser or native RSAT.app connects to Nginx on localhost and the FastAPI control plane. PostgreSQL holds encrypted settings, operator accounts, switch inventory and audit events; its schema is managed by Alembic migrations (`backend/app/migrations`) applied at start-up. The API authenticates operators with a revocable session cookie and applies role permissions to both connection modes.

## Request path

1. `app/auth.py` resolves the session (cookie or bearer token), checks it against the operator's current state and enforces the permission required by the route.
2. Routers validate input with Pydantic models and call the connector through `app/worker_client.py`, which dispatches to demo fixtures, the direct connectors or the Windows worker.
3. Write routes go through `app/audit.py::audited`, which records the outcome — `success`, `failed` or `demo` — with redacted details.

## Direct Mac/Linux mode

- AD directory reads and common writes use LDAPS with CA validation or explicit certificate pinning before credentials are sent. Bound connections are pooled briefly and re-validated before reuse.
- Kerberos tickets for the RPC connectors are obtained once and reused for a few minutes (`app/kerberos_cache.py`).
- DNS zone/record inventory uses LDAP; record writes use Samba DNS RPC.
- DHCP discovery uses LDAP and service operations use Impacket MS-DHCPM RPC.
- Both RPC paths require Kerberos and packet privacy, with private temporary credential caches.
- SSH switch terminals use verified host keys and single-use WebSocket tickets.

See [direct mode](direct-mac.md) for implemented operations and limitations. Optional WinRM service access requires Kerberos and encrypted messages. No native connector provides a generic command execution API.

## Optional Windows worker

Microsoft RSAT PowerShell modules require Windows. A dedicated domain-joined management host executes allow-listed operations for worker mode, including additional Group Policy and directory features. The channel is HTTPS: the worker's certificate fingerprint is confirmed by the operator at pairing and pinned (`app/worker_tls.py`). Pairing exchanges a one-time code for an encrypted worker credential; the worker uses its Windows account token. It does not expose arbitrary PowerShell execution.

## Native macOS launcher

The AppKit/WebKit app runs a fixed startup helper off the UI thread, reuses the existing Colima profile and Compose project, checks health and opens the local panel. Its generated configuration records the local clone path; it embeds no passwords. Closing the app leaves services and persistent data intact.
