# Architecture

The browser or native RSAT.app connects to Nginx on localhost and the FastAPI control plane. PostgreSQL holds encrypted settings, switch inventory and audit events. The API applies JWT authentication and role permissions to both connection modes.

## Direct Mac/Linux mode

- AD directory reads and common writes use LDAPS with CA validation or explicit certificate pinning before credentials are sent.
- DNS zone/record inventory uses LDAP; record writes use Samba DNS RPC.
- DHCP discovery uses LDAP and service operations use Impacket MS-DHCPM RPC.
- Both RPC paths require Kerberos and packet privacy, with private temporary credential caches.
- SSH switch terminals use verified host keys and single-use WebSocket tickets.

See [direct mode](direct-mac.md) for implemented operations and limitations. Optional WinRM service access requires Kerberos and encrypted messages. No native connector provides a generic command execution API.

## Optional Windows worker

Microsoft RSAT PowerShell modules require Windows. A dedicated domain-joined management host executes allow-listed operations for worker mode, including additional Group Policy and directory features. Pairing exchanges a one-time code for an encrypted worker credential; the worker uses its Windows account token. It does not expose arbitrary PowerShell execution.

## Native macOS launcher

The AppKit/WebKit app runs a fixed startup helper off the UI thread, reuses the existing Colima profile and Compose project, checks health and opens the local panel. Its generated configuration records the local clone path; it embeds no passwords. Closing the app leaves services and persistent data intact.
