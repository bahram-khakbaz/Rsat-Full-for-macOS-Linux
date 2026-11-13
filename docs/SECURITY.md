# Security model

## Publication hygiene

Keep real connection settings, host inventories, credentials, LDAP/DNS exports,
logs, screenshots, recordings, database backups and built local app bundles out
of GitHub. The app bundle records the local checkout path. Never package the
private `.env`, database volume or local `outputs` folder in a release.

Before pushing or publishing, run from the repository root:

```bash
python3 scripts/check-publication.py --history
gitleaks git --redact --no-banner --log-opts=--all .
```

Install Gitleaks from its [official repository](https://github.com/gitleaks/gitleaks).
The path guard checks the Git index and reachable history without reading private
untracked runtime data. Gitleaks scans committed content for recognized secrets;
also scan staged changes with `gitleaks git --staged --redact --no-banner .` before
committing. Neither tool understands every organization's confidential data.
Review staged diffs for real hostnames, IP inventories, account names and business
content as well. Demo/test fixtures must remain synthetic.

The Publication hygiene workflow runs the path guard and a checksum-verified,
pinned Gitleaks release over full history. CI detects problems after a push;
run the local checks first to avoid publishing a secret in the first place.
`.gitignore` reduces accidental inclusion but is not a security boundary.

If a real secret was committed, remove it from current files, revoke/rotate it,
and assess every branch, tag and release. Deleting a file in a later commit does
not remove its history. History cleanup requires coordination with collaborators
and cannot recall copies already downloaded.

This repository intentionally contains no organization-specific domain names, IP addresses, credentials, API keys, or tokens.

## Identity separation

There are two separate identities:

1. **Web operator identity** — the person using the RSAT Full UI.
2. **Windows Worker identity** — the Windows domain account that executes Microsoft RSAT commands.

Web operators are either the environment-managed administrator (`ADMIN_USERNAME` / `ADMIN_PASSWORD`, a break-glass account) or panel operators created under **Settings → Operators** with one role each. Operator passwords are stored as salted scrypt hashes. Because every operator acts through the same saved directory account or worker identity, the panel audit log is the record of who did what.

Worker mode uses the Windows account token. Direct mode stores the configured domain password encrypted with Fernet in PostgreSQL; saved passwords are never returned to the frontend or audit log. JWT_SECRET derives the encryption key: keep it stable, protect `.env` and database backups, and do not rotate it without a credential migration. SSH credentials use the same encrypted store.

Direct LDAPS validates a trusted CA or an explicitly approved certificate pin, hostname and validity period before binding. DNS/DHCP RPC requires Kerberos and packet privacy. Tickets use private, short-lived temporary caches removed after requests. SSH verifies the approved server host key before password authentication, uses single-use session tickets and does not log terminal text.

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

- Sessions are signed tokens in an httpOnly, SameSite=Strict cookie scoped to `/api`; state-changing requests made with the cookie must be same-origin. A bearer header is accepted for API clients.
- Every session is checked against the account on each request: disabling an operator, resetting a password, changing a role or "sign out everywhere" takes effect immediately.
- Sign-in is throttled per account and per client: after `LOGIN_MAX_FAILURES` (default 5) failures the account is locked for `LOGIN_LOCKOUT_SECONDS` (default 900), doubling on further failures. The counters live in the backend process and reset when it restarts.
- Role-permission matrix in the API, assignable to panel operators.
- Production start-up fails while `JWT_SECRET`, `ADMIN_PASSWORD` or `ENCRYPTION_KEY` hold example values.
- No arbitrary PowerShell execution endpoint.
- PowerShell values are passed through environment variables instead of being interpolated into command strings.
- Privileged write operations are recorded in PostgreSQL audit logs with their outcome: `success`, `failed` (with the error returned to the operator) or `demo`. Failed sign-ins are recorded too.
- Worker traffic is HTTPS with a certificate pinned at pairing; the worker credential is only ever sent to the paired URL.
- Backend and web containers run as unprivileged users without Linux capabilities. Nginx sends Content-Security-Policy, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`.
- Password reset values are never written into audit details.
- Local Docker deployment binds the web UI to `127.0.0.1` by default.
- Worker pairing is rate-limited and single-use.
- Per-DC health tests validate DNS, LDAP, Kerberos, SMB, LDAPS and Global Catalog reachability.

## Production requirements

Before organizational production use:

- Serve the panel over TLS (reverse proxy) if it is reachable beyond localhost, and set `CORS_ORIGINS` to that origin.
- Add organizational OIDC/SAML/SSO with MFA in front of the panel; local operator accounts have no second factor.
- Run the Worker under a delegated service account or gMSA.
- Restrict the Worker network port to the control-plane host.
- Keep Worker traffic on HTTPS (the default). Do not set `ALLOW_INSECURE_WORKER=true` outside an isolated lab.
- Back up PostgreSQL.
- Ship audit events to central logging/SIEM.
- Delegate only the AD/DNS/DHCP/GPO permissions the Worker actually needs.

## Credential encryption keys

Stored AD, SSH and worker credentials are encrypted with Fernet. The key is derived from:

- `ENCRYPTION_KEY` (HKDF-SHA256) when it is set — new installations generate one; or
- `JWT_SECRET` (legacy derivation) when `ENCRYPTION_KEY` is empty, which keeps installations created before 1.4.0 working unchanged.

To move an existing installation to a dedicated key, set `ENCRYPTION_KEY` to at least 32 random characters and restart. Values still readable with the old key are re-encrypted under the new one at start-up; the legacy `JWT_SECRET` key remains accepted for reading, so keep `JWT_SECRET` unchanged until the start-up log reports the re-encryption.

To rotate later, move the current value to `ENCRYPTION_KEY_PREVIOUS` (comma-separated list, read-only keys), set a new `ENCRYPTION_KEY` and restart. Remove the previous key after the next successful start. A credential that cannot be decrypted with any configured key is reported in the backend log and must be saved again in the panel; it is never silently replaced.

Kerberos tickets for direct DNS/DHCP calls are held in a private temporary directory inside the backend container and reused for up to three minutes (ticket lifetime five minutes). They are discarded when the saved account changes or an operation fails.
