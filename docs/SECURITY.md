# Security model

This repository intentionally contains no organization-specific domain names, IP addresses, credentials, API keys, or tokens.

## Identity separation

There are two separate identities:

1. **Web operator identity** — the person using the RSAT Full UI.
2. **Windows Worker identity** — the Windows domain account that executes Microsoft RSAT commands.

The macOS/Linux control plane does not store the operator's Active Directory password.

For production, the Windows Worker should run under a delegated service account or gMSA with the minimum required AD/DNS/DHCP/GPO permissions.

## Worker pairing

The operator never manually configures the internal Worker API secret.

- `run-worker.ps1` generates the persistent high-entropy Worker secret automatically.
- Every Worker start generates a separate one-time pairing code.
- The pairing code is held in process memory, expires after 15 minutes, and can be used once.
- During pairing, the backend receives the Worker credential and stores it encrypted with Fernet.
- The UI never receives or displays the internal Worker credential.
- Changing the configured Worker URL clears the saved pairing and requires a new pair operation.

## Implemented controls

- Authenticated control-plane API using expiring JWTs.
- Role-permission matrix in the API.
- No arbitrary PowerShell execution endpoint.
- PowerShell values are passed through environment variables instead of being interpolated into command strings.
- Privileged write operations are recorded in PostgreSQL audit logs.
- Password reset values are never written into audit details.
- Local Docker deployment binds the web UI to `127.0.0.1` by default.
- Worker pairing is rate-limited and single-use.
- Per-DC health tests validate DNS, LDAP, Kerberos, SMB, LDAPS and Global Catalog reachability.

## Production requirements

Before organizational production use:

- Replace local admin login with organizational OIDC/SAML/SSO.
- Run the Worker under a delegated service account or gMSA.
- Restrict the Worker network port to the control-plane host.
- Enable TLS for Worker traffic when it crosses a shared/untrusted network segment.
- Back up PostgreSQL.
- Ship audit events to central logging/SIEM.
- Delegate only the AD/DNS/DHCP/GPO permissions the Worker actually needs.
