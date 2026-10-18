# Optional Vault Agent credential delivery

RSAT stores an operator-scoped reference instead of an encrypted password when
Vault Agent mode is selected. This is an Agent integration, not a direct Vault
HTTP client. RSAT never receives a Vault token. Agent authentication, TLS, policies
and secret rotation remain administrator responsibilities. Existing installations
keep their local encrypted credentials; no automatic migration is performed.

Consumers: direct AD and its DNS/DHCP Kerberos operations, SSH switches, Linux SSH
and SFTP. The worker channel token and panel administrator password are outside
this provider. gMSA is a separate Windows Worker identity mechanism.

## Setup

1. Provision Vault Agent externally with verified TLS, an approved auto-auth method
   and a least-privilege policy for the required secrets. Keep its config private.
2. Obtain the namespace for the **panel account**, not the AD/SSH username:

   ```bash
   docker compose exec backend python -c 'from app.vault_agent import namespace; print(namespace("operator"))'
   ```

3. Create a private delivery root and a subdirectory named with that 64-character
   namespace. Neither may be group/world writable. Use a memory-backed filesystem
   where practical; mount only this delivery directory into RSAT.
4. Add a template to your Agent configuration; replace the example namespace,
   destination and Vault KV v2 secret path:

   ```hcl
   template_config {
     static_secret_render_interval = "60s"
     exit_on_retry_failure = true
   }
   template {
     destination = "/private/delivery/OWNER_NAMESPACE/ad-password.json"
     perms = "0600"
     error_on_missing_key = true
     contents = <<EOF
   {{- with secret "secret/data/rsat/example-ad" -}}
   {"password": {{ .Data.data.password | toJSON }}, "rendered_at": "{{ timestamp }}"}
   {{- end -}}
   EOF
   }
   ```

   Confirm that the deployed Agent refreshes the timestamp even when the password
   is unchanged. A static copied JSON file is not a production delivery.

5. Set `RSAT_VAULT_DELIVERY_DIR` to the private delivery root and deploy:

   ```bash
   docker compose -f docker-compose.yml -f compose.vault.example.yaml up -d --build
   ```

6. In AD Settings or a switch/Linux credential form, leave Password blank and enter
   the logical **Vault Agent key** (`ad-password`, without `.json`). Keys cannot be
   file paths. To switch back, clear the key and enter a local password. Leaving
   both blank preserves the current credential.

The saving panel account determines the namespace. Sharing credentials between
operators requires separately authorized deliveries in each namespace; the form
cannot select another operator's directory.

## Guarantees and limits

- Each credential use reopens the file; atomic rotations need no database update.
  Existing authenticated sessions continue; new authentications read the delivery.
- Missing, invalid or stale files fail with a generic 503, never a local fallback.
  Messages exclude credential contents and private filenames.
- Default freshness window: 180 seconds; `VAULT_MAX_AGE_SECONDS` permits 30–3600.
  This is not instant revocation. Timestamps over 30 seconds in the future fail.
- Agent handles retrieval/renewal. RSAT trusts the authorized file producer and
  cannot independently prove that a timestamp reflects a successful Vault read.
- Deliveries must be bounded, regular JSON files with owner-only permission bits.
  Symlinks are rejected. This consumer requires the POSIX backend, normally Docker
  on Linux, rather than the Windows worker.
- The password exists transiently in backend memory and in the protected delivery
  file. This does not claim that no plaintext copy exists anywhere.

Do not commit deliveries, real Vault paths/policies, tokens or organization data.
Protect the database (provider references) and the separate secret mount.

References: [Vault Agent templates](https://developer.hashicorp.com/vault/docs/agent-and-proxy/agent/template),
[auto-auth](https://developer.hashicorp.com/vault/docs/agent-and-proxy/autoauth),
[timestamp function](https://developer.hashicorp.com/consul/docs/reference/consul-template/go).
