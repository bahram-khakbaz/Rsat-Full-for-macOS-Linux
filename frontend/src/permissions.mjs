// Pure helpers for the role-permission list returned by GET /api/auth/me.
// The API enforces every permission; these only decide what the UI offers.

/** Permission each navigation section needs before it is shown. */
export const SECTION_PERMISSIONS = {
  overview: 'domain.read',
  domain: 'domain.read',
  users: 'ad.read',
  groups: 'group.read',
  computers: 'computer.read',
  ous: 'ou.read',
  recycle: 'ad.read',
  dns: 'dns.read',
  dhcp: 'dhcp.read',
  gpo: 'gpo.read',
  audit: 'audit.read',
  ssh: 'ssh.read',
  linux: 'ssh.read',
  'ssh-sessions': 'ssh.connect',
  files: 'sftp.read',
  settings: 'settings.read',
};

export function hasPermission(permissions, name) {
  if (!Array.isArray(permissions) || !name) return false;
  return permissions.includes('*') || permissions.includes(name);
}

export function canOpenSection(permissions, section) {
  const required = SECTION_PERMISSIONS[section];
  return required ? hasPermission(permissions, required) : false;
}

/** The requested section when permitted, otherwise the first permitted one. */
export function resolveSection(permissions, requested, order) {
  if (canOpenSection(permissions, requested)) return requested;
  return order.find((section) => canOpenSection(permissions, section)) || null;
}

/** How an audit row's status is presented: Status `ok` flag plus a short label. */
export function auditStatus(status) {
  switch (status) {
    case 'success':
      return { ok: true, label: 'Command completed' };
    case 'failed':
      return { ok: false, label: 'Failed' };
    case 'demo':
      return { ok: null, label: 'Demo only (not applied)' };
    case 'requested':
      return { ok: null, label: 'Requested' };
    default:
      return { ok: null, label: 'Check result' };
  }
}
