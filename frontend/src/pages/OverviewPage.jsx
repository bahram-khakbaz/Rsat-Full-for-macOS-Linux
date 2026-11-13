import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Status } from '../components/Status.jsx';
import { Table } from '../components/Table.jsx';
import { Panel } from '../components/Panel.jsx';
import { KV } from '../components/KV.jsx';
import { useSession } from '../session.jsx';

export function Overview({ notify, native = false }) {
  const { can } = useSession();
  const [data, setData] = useState(null),
    [loading, setLoading] = useState(true);
  async function load() {
    setLoading(true);
    try {
      const names = [
        '/api/domain/summary',
        '/api/ad/users',
        '/api/ad/computers',
        '/api/dns/zones',
        '/api/dhcp/scopes',
        '/api/domain/replication',
      ];
      // A null entry is not requested: the role cannot read it, or (replication)
      // direct mode has no such endpoint.
      const paths = [
        can('domain.read') ? names[0] : null,
        can('ad.read') ? names[1] + '?page_size=100' : null,
        can('computer.read') ? names[2] : null,
        can('dns.read') ? names[3] : null,
        can('dhcp.read') ? names[4] : null,
        can('domain.read') && !native ? names[5] : null,
      ];
      const results = await Promise.allSettled(
        paths.map((apiPath) =>
          apiPath ? api(apiPath) : Promise.reject(new Error('Not requested')),
        ),
      );
      const value = (i, fallback) =>
        results[i].status === 'fulfilled' ? results[i].value : fallback;
      const userPage = value(1, []);
      const users = Array.isArray(userPage) ? userPage : userPage?.items || [];
      // Locked/disabled counts are only meaningful when this page holds every user.
      const usersComplete =
        results[1].status === 'fulfilled' && (Array.isArray(userPage) || !userPage?.has_more);
      setData({
        d: value(0, {}),
        u: users,
        userTotal:
          typeof userPage?.total === 'number'
            ? userPage.total
            : usersComplete
              ? users.length
              : null,
        userTotalsAvailable: usersComplete,
        c: value(2, []),
        z: value(3, []),
        s: value(4, []),
        r: value(5, []),
        online: results[0].status === 'fulfilled',
        unavailable: names.filter((_, i) => results[i].status === 'rejected'),
      });
      if (paths[0] && results[0].status === 'rejected') notify(results[0].reason.message, 'bad');
    } catch (e) {
      notify(e.message, 'bad');
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  if (loading)
    return (
      <Panel title="SYSTEM SCAN" code="WAIT">
        <div className="loading">READING DIRECTORY SERVICES...</div>
      </Panel>
    );
  if (!data)
    return (
      <div className="error-box">
        Directory unavailable. Open Settings to configure the connection.
      </div>
    );
  const locked = data.u.filter((x) => x.lockedOut).length,
    disabled = data.u.filter((x) => !x.enabled).length,
    repFail = data.r.reduce((a, x) => a + Number(x.failures || 0), 0);
  return (
    <div className="stack">
      <div className="hero-console">
        <div>
          <span className="eyebrow">CONTROL PLANE / READY</span>
          <h2>{data.d.domain}</h2>
          <p>
            {data.d.forest} · {data.d.domainMode} · {data.d.forestMode}
          </p>
        </div>
        <div className="big-status">
          {data.online ? 'ONLINE' : 'OFFLINE'}
          <span>●</span>
        </div>
      </div>
      {can('ad.read') && !data.userTotalsAvailable && (
        <div className="identity-model-note">
          <span>
            Users are browsed and searched by page. Locked and disabled counts require a full
            directory scan and are not inferred from the first page.
          </span>
        </div>
      )}
      <div className="metrics">
        {[
          ['DIRECTORY USERS', data.userTotal ?? '—', 'USR'],
          ['LOCKED ACCOUNTS', data.userTotalsAvailable ? locked : '—', 'LCK'],
          ['DISABLED USERS', data.userTotalsAvailable ? disabled : '—', 'DSB'],
          [
            'COMPUTERS',
            data.unavailable.includes('/api/ad/computers') ? 'N/A' : data.c.length,
            'CMP',
          ],
          ['DNS ZONES', data.unavailable.includes('/api/dns/zones') ? 'N/A' : data.z.length, 'DNS'],
          [
            'DHCP SCOPES',
            data.unavailable.includes('/api/dhcp/scopes') ? 'N/A' : data.s.length,
            'DHC',
          ],
          [
            'REPL. FAILURES',
            data.unavailable.includes('/api/domain/replication') ? 'N/A' : repFail,
            'REP',
          ],
          [
            'RECYCLE BIN',
            data.d.recycleBin == null ? 'UNKNOWN' : data.d.recycleBin ? 'ON' : 'OFF',
            'RCY',
          ],
        ].map((x) => (
          <div className="metric" key={x[0]}>
            <span>{x[2]}</span>
            <strong>{x[1] ?? '—'}</strong>
            <small>{x[0]}</small>
          </div>
        ))}
      </div>
      <div className="grid-2">
        <Panel title="FSMO ROLE OWNERS" code="FSMO">
          <KV
            items={[
              ['PDC EMULATOR', data.d.pdc],
              ['RID MASTER', data.d.rid],
              ['INFRASTRUCTURE', data.d.infrastructure],
              ['SCHEMA MASTER', data.d.schema],
              ['NAMING MASTER', data.d.naming],
            ]}
          />
        </Panel>
        <Panel
          title="REPLICATION STATUS"
          code="REPL"
          actions={
            <Button icon={RefreshCw} onClick={load}>
              REFRESH
            </Button>
          }
        >
          <Table
            empty="Replication data unavailable"
            rows={data.r.slice(0, 8)}
            rowKey="server"
            cols={[
              { key: 'server', label: 'SERVER' },
              { key: 'partner', label: 'PARTNER' },
              { key: 'failures', label: 'FAIL' },
              {
                key: 'status',
                label: 'STATE',
                render: (v) => <Status ok={v === 'Healthy'}>{v}</Status>,
              },
            ]}
          />
        </Panel>
      </div>
    </div>
  );
}
