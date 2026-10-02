# Security model

This repository intentionally contains no organization-specific domain names, IP addresses, credentials, API keys, or tokens.

## Implemented controls

- Authenticated API using expiring JWTs.
- Role-permission matrix in the API.
- Separate Windows worker token.
- No arbitrary PowerShell endpoint.
- PowerShell values are passed through environment variables instead of being interpolated into command strings.
- Privileged write operations are recorded in PostgreSQL audit logs.
- Password reset values are never written into audit details.
- Local Docker deployment binds the web UI to `127.0.0.1` by default.

## Before organizational production use

Replace local admin login with OIDC/SAML/SSO, enable HTTPS, apply least-privilege delegation to the worker identity, restrict network access, back up PostgreSQL, and ship audit events to the organization's central logging platform.
