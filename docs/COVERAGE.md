# Management coverage

RSAT Full is a web-native administration center for the common Active Directory administration stack. It does not ship or emulate Microsoft MMC binaries.

## Connection modes

The inventories below describe Windows worker coverage. Direct Mac/Linux mode supports directory reads and common LDAP writes, DNS record inventory/create/edit/delete for eight types, and IPv4 DHCP scope and reservation management. It does not provide user creation, protected OU creation, replication health, recycle-bin restore, full GPO management, DNS zone management or DHCP utilization/options/failover. See [the detailed direct-mode coverage](direct-mac.md). SSH terminals and the native macOS app are independent of the Windows worker.

## Active Directory

Implemented:

- Domain and forest summary
- FSMO role discovery
- Domain controller inventory
- Replication status
- Trust inventory
- Site/subnet inventory
- Default domain password policy
- Fine-grained password policy inventory
- Recycle Bin browsing and restore
- User list/search/detail/create/update/delete
- Unlock / enable / disable
- Password reset
- Account options: password never expires, password change at next logon, account expiry / never expires, smart-card requirement, sensitive/not-delegated and logon workstations (direct mode and updated worker)
- Last-modified timestamp (`whenChanged`), with queried DC identity in direct mode
- Move user between OUs
- User group memberships
- Group list/create/delete
- Group members add/remove
- Computer list/search/enable/disable/reset/move/delete
- OU list/create/delete

These account options do not provide complete ADUC property parity. Password-change ACLs, logon-hour scheduling, delegation grants, security descriptors, certificates and RDS/COM+ settings are not implemented by the account-options dialog. Password expiration dates are computed by AD policy; only account expiration is directly editable. See [User account options](../README.md#user-account-options) for validation and test limitations.

## DNS

Implemented:

- Zone inventory
- AD-integrated primary zone create/delete
- A, AAAA, CNAME and PTR inventory
- A, AAAA, CNAME and PTR create/delete

## DHCP

Implemented:

- IPv4 scope inventory and statistics
- Scope create/delete
- Scope activate/deactivate
- Lease inventory
- Reservation inventory/create/delete

## Group Policy

Implemented:

- GPO inventory/create/delete
- Link inventory
- Link/unlink to domain or OU
- Enforced/enabled/order controls when linking
- GPO status
- Backup
- XML report
- Permission inventory
- Permission updates/security filtering foundation

## Platform capabilities

- macOS/Linux web UI
- Windows RSAT worker
- Docker Compose
- Demo mode
- RBAC
- JWT sessions
- PostgreSQL audit log
- Allow-listed worker API
- CI build/test workflow
- Offline-safe UI assets

## Not claimed as implemented

A single project called "RSAT" covers many independent Microsoft server products. These specialized consoles are intentionally outside the current scope:

- Active Directory Certificate Services
- DFS Management
- Failover Clustering
- Network Policy Server
- WSUS
- Hyper-V Manager
- File Services / FSRM
- Storage Migration Service
- Remote Desktop Services management
- IPAM
- Windows Server Backup
- every third-party or role-specific MMC extension

Those can be added as separate worker modules without changing the cross-platform architecture.
