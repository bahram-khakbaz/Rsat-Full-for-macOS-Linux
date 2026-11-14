import { auditStatus } from '../permissions.mjs';

export function DomainStatus({ shell }) {
  const s = shell.summary || {},
    dcs = shell.controllers || [],
    repl = shell.replication || [];
  const healthy = repl.length > 0 && repl.every((x) => Number(x.failures || 0) === 0);
  return (
    <section className="bottom-window">
      <div className="window-title">
        <span>DOMAIN STATUS</span>
        <span>⌃</span>
      </div>
      <div className="status-list">
        <div>
          <i />
          <span>Domain:</span>
          <b>{s.domain || '—'}</b>
        </div>
        <div>
          <i />
          <span>Domain Functional Level:</span>
          <b>{s.domainMode || '—'}</b>
        </div>
        <div>
          <i />
          <span>Forest Functional Level:</span>
          <b>{s.forestMode || '—'}</b>
        </div>
        <div>
          <i />
          <span>Domain Controllers:</span>
          <b>{shell.summary ? dcs.length : '—'}</b>
        </div>
        <div>
          <i />
          <span>Global Catalog:</span>
          <b>{shell.summary ? dcs.filter((x) => x.globalCatalog).length : '—'}</b>
        </div>
        <div>
          <i />
          <span>FSMO Roles:</span>
          <b className="green-text">{s.pdc ? 'Owner known' : 'Unknown'}</b>
        </div>
        <div>
          <i className={healthy ? '' : 'err'} />
          <span>Replication:</span>
          <b className={healthy ? 'green-text' : 'red-text'}>
            {!repl.length ? 'Unavailable' : healthy ? 'Healthy' : 'Attention'}
          </b>
        </div>
      </div>
    </section>
  );
}

export function RecentActivity({ rows = [] }) {
  return (
    <section className="bottom-window">
      <div className="window-title">
        <span>RECENT ACTIVITY</span>
        <span>⌃</span>
      </div>
      <div className="mini-table-wrap">
        <table className="mini-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>User</th>
              <th>Action</th>
              <th>Target</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 8).map((r) => (
              <tr key={r.id}>
                <td>
                  {r.at
                    ? new Date(r.at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })
                    : '—'}
                </td>
                <td>{r.actor}</td>
                <td>{r.action}</td>
                <td>{r.target || '—'}</td>
                <td>{auditStatus(r.status).label}</td>
              </tr>
            ))}
            {!rows.length && (
              <tr>
                <td colSpan="5">No audit events loaded</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function SystemConsole({ shell, section }) {
  const now = new Date().toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
  const domain = shell.summary?.domain || '—';
  const dc = shell.controllers?.[0]?.hostName || shell.controllers?.[0]?.name || '—';
  const demo = shell.health?.demo_mode;
  const lines = [
    `[${now}] Connected to control plane ........ OK`,
    `[${now}] Directory API ..................... ${shell.summary ? 'OK' : 'UNAVAILABLE'}`,
    `[${now}] Audit subsystem ................... ${shell.audit ? 'OK' : 'N/A'}`,
    `[${now}] Domain: ${domain}`,
    `[${now}] DC: ${dc}`,
    `[${now}] Mode: ${demo ? 'DEMO' : shell.health?.connection_mode === 'native' ? 'DIRECT MAC / LDAPS' : 'WINDOWS WORKER'}`,
    `[${now}] Module: ${section.toUpperCase()}`,
    `[${now}] Session ready`,
  ];
  return (
    <section className="bottom-window console-window">
      <div className="window-title">
        <span>SYSTEM CONSOLE</span>
        <span>⋮</span>
      </div>
      <pre>
        {lines.map((x, i) => (
          <span key={i} className={i < 3 ? 'console-ok' : ''}>
            {x}
            {'\n'}
          </span>
        ))}
      </pre>
    </section>
  );
}

export function BottomDock({ shell, section }) {
  return (
    <div className="bottom-dock">
      <DomainStatus shell={shell} />
      <RecentActivity rows={shell.audit} />
      <SystemConsole shell={shell} section={section} />
    </div>
  );
}
