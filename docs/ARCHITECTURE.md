# Architecture

RSAT Full Admin Center separates the cross-platform control plane from privileged Windows execution.

```text
macOS / Linux browser
        |
        | HTTPS
        v
Web UI (React + Nginx)
        |
        v
Control API (FastAPI)
  |             |
  |             +--> PostgreSQL audit log
  |
  +--> trusted private network / TLS
             |
             v
      Windows Admin Worker
        domain joined
             |
   allow-listed PowerShell only
             |
   +---------+---------+---------+
   |         |         |         |
   AD      DNS       DHCP      GPO
```

## Why a Windows worker exists

macOS and Linux do not provide Microsoft's RSAT PowerShell modules. The web application therefore does not try to emulate them locally. A dedicated domain-joined Windows management host executes a strict set of known commands and returns structured JSON.

## Trust boundaries

1. Browser to web: authenticated user session.
2. Web to API: JWT bearer token and RBAC.
3. API to worker: dedicated high-entropy worker token over a trusted private network or TLS reverse proxy.
4. Worker to domain services: Windows integrated credentials or a delegated service identity.

The worker does **not** expose arbitrary PowerShell execution.
