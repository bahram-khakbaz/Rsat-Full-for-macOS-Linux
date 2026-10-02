# Management coverage

The project is a cross-platform replacement for common daily RSAT administration workflows, not a binary port of Microsoft's MMC consoles.

## Implemented

- Active Directory user search and details
- Account unlock, enable, disable and password reset APIs
- Group inventory
- Computer inventory
- OU inventory
- DNS record inventory and A/AAAA/CNAME creation API
- DHCP scope statistics and reservation creation API
- GPO inventory and GPO creation API
- RBAC enforcement
- PostgreSQL audit logging
- macOS/Linux Docker deployment
- Windows RSAT worker
- Demo mode for offline development

## Deliberately delegated to native Microsoft tooling

A complete Group Policy editor, schema/forest operations, AD CS, DFS, Failover Clustering, and every MMC snap-in remain outside the current release. The worker architecture is modular so additional allow-listed capabilities can be added safely.
