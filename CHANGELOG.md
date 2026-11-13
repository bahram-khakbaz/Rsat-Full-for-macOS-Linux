# Changelog

## 1.4.0

Security and maintenance release. **Read "Action required" before updating.**

### Action required

- **Windows worker must be updated and paired again.** The worker now serves HTTPS with its own certificate and the control plane refuses `http://` worker URLs. Install the updated worker, start it, then in **Settings** inspect the certificate, compare the SHA-256 fingerprint with the one printed on the worker console and pair again. `ALLOW_INSECURE_WORKER=true` restores plain HTTP for an isolated lab only.
- **Rebuild both images** (`docker compose up -d --build --wait`). The web container now listens on 8080 internally; the published address is still `http://localhost:8080`.
- **Sign in again.** Sessions moved from browser storage to an httpOnly cookie.
- **Vault Agent users:** the backend no longer runs as root. Set `RSAT_BACKEND_UID`/`RSAT_BACKEND_GID` to the owner of the delivered files, or run the agent as UID 10001.
- Production start-up is refused if `JWT_SECRET` (minimum 32 characters), `ADMIN_PASSWORD` or `ENCRYPTION_KEY` still hold example values.
- Developers: test tooling moved to `backend/requirements-dev.txt`.

### Security

- Panel operators with roles, managed in Settings; salted scrypt password hashes.
- httpOnly SameSite=Strict session cookie, same-origin check for state-changing requests, immediate session revocation, "sign out everywhere".
- Sign-in lockout per account and per client; failed sign-ins are audited.
- Dedicated `ENCRYPTION_KEY` for stored credentials with rotation support; undecryptable credentials are reported instead of silently treated as empty.
- Worker channel over pinned TLS; the worker credential is only sent to the paired URL, and is cleared whenever the worker URL changes.
- Failed and rejected write operations are audited; demo-mode writes are marked `demo`.
- Identities are percent-encoded when forwarded to a connector, so they cannot alter the route.
- Containers run unprivileged with capabilities dropped; nginx sends CSP and related headers; the compiler is no longer shipped in the backend image.

### Fixed

- Sign-in with non-ASCII characters returned HTTP 500.
- Worker mode stripped or rejected non-Latin names, silently truncated users (500), DNS zones (30) and records (1,000), and accepted only four DNS record types.
- A paged user list is available in every connection mode.
- Empty optional query parameters are no longer sent to the worker.
- Product version is reported consistently (backend, UI, worker, macOS app).

### Added

- VLAN rename, default-status change and delete.
- Group search.
- Alembic migrations applied at start-up; databases created by earlier versions are adopted in place.
- Reuse of authenticated LDAPS connections and Kerberos tickets in direct mode.
- `ruff` lint/format configuration and CI checks; container build and start-up smoke test in CI.
