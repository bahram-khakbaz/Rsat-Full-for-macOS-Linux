import { useEffect, useState } from 'react';
import { RefreshCw, Wifi } from 'lucide-react';
import { api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Status } from '../components/Status.jsx';
import { Table } from '../components/Table.jsx';
import { Panel } from '../components/Panel.jsx';
import { KV } from '../components/KV.jsx';

export function Domain({ notify, native = false }) {
  const [state, setState] = useState({
      summary: null,
      controllers: [],
      replication: [],
      trusts: [],
      sites: [],
      subnets: [],
      policy: null,
      fgpp: [],
    }),
    [loading, setLoading] = useState(true);
  async function load() {
    setLoading(true);
    try {
      const keys = [
        'summary',
        'controllers',
        'replication',
        'trusts',
        'sites',
        'subnets',
        'policy',
        'fgpp',
      ];
      const results = await Promise.allSettled(
        [
          '/summary',
          '/controllers',
          '/replication',
          '/trusts',
          '/sites',
          '/subnets',
          '/password-policy',
          '/password-policies',
        ].map((x) =>
          // Direct mode has no replication endpoint (always 501): do not request it.
          native && x === '/replication'
            ? Promise.reject(new Error('Unavailable in direct mode'))
            : api('/api/domain' + x),
        ),
      );
      setState(
        Object.fromEntries(
          keys.map((key, i) => [
            key,
            results[i].status === 'fulfilled' ? results[i].value : i === 0 || i === 6 ? null : [],
          ]),
        ),
      );
      const failed = results.filter((r, i) => r.status === 'rejected' && i !== 2);
      if (failed.length) notify(failed[0].reason.message, 'bad');
    } catch (e) {
      notify(e.message, 'bad');
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  if (loading) return <div className="loading">QUERYING DOMAIN CONTROLLERS...</div>;
  const s = state.summary || {},
    p = state.policy || {};
  return (
    <div className="stack">
      <Panel
        title="DOMAIN / FOREST IDENTITY"
        code="ROOT"
        actions={
          <Button icon={RefreshCw} onClick={load}>
            REFRESH
          </Button>
        }
      >
        <KV
          items={[
            ['DOMAIN', s.domain],
            ['FOREST', s.forest],
            ['DOMAIN MODE', s.domainMode],
            ['FOREST MODE', s.forestMode],
            [
              'RECYCLE BIN',
              s.recycleBin == null ? 'UNKNOWN' : s.recycleBin ? 'ENABLED' : 'DISABLED',
            ],
          ]}
        />
      </Panel>
      <Panel title="DOMAIN CONTROLLERS" code="DC">
        <Table
          rows={state.controllers}
          rowKey="name"
          cols={[
            { key: 'name', label: 'NAME' },
            { key: 'site', label: 'SITE' },
            { key: 'ipv4', label: 'IPV4' },
            { key: 'os', label: 'OS' },
            {
              key: 'globalCatalog',
              label: 'GC',
              render: (v) => <Status ok={v}>{v ? 'YES' : 'NO'}</Status>,
            },
          ]}
        />
      </Panel>
      <div className="grid-2">
        <Panel title="DEFAULT DOMAIN PASSWORD POLICY" code="PASS">
          <KV
            items={[
              ['MIN LENGTH', p.minPasswordLength],
              ['MAX AGE / DAYS', p.maxPasswordAgeDays],
              ['HISTORY', p.passwordHistoryCount],
              ['COMPLEXITY', p.complexityEnabled ? 'ENABLED' : 'DISABLED'],
              ['LOCKOUT THRESHOLD', p.lockoutThreshold],
              ['LOCKOUT DURATION / MIN', p.lockoutDurationMinutes],
            ]}
          />
        </Panel>
        <Panel title="FINE-GRAINED PASSWORD POLICIES" code="FGPP">
          <Table
            rows={state.fgpp}
            rowKey="name"
            cols={[
              { key: 'name', label: 'POLICY' },
              { key: 'precedence', label: 'PRECEDENCE' },
              { key: 'minPasswordLength', label: 'MIN LEN' },
              { key: 'maxPasswordAgeDays', label: 'MAX AGE' },
              { key: 'lockoutThreshold', label: 'LOCKOUT' },
            ]}
          />
        </Panel>
      </div>
      <div className="grid-2">
        <Panel title="TRUSTS" code="TRST">
          <Table
            rows={state.trusts}
            rowKey="name"
            cols={[
              { key: 'name', label: 'TRUST' },
              { key: 'direction', label: 'DIRECTION' },
              { key: 'type', label: 'TYPE' },
              {
                key: 'transitive',
                label: 'TRANSITIVE',
                render: (v) => <Status ok={v}>{v ? 'YES' : 'NO'}</Status>,
              },
            ]}
          />
        </Panel>
        <Panel title="SITES / SUBNETS" code="SITE">
          <Table
            rows={state.sites}
            rowKey="name"
            cols={[
              { key: 'name', label: 'SITE' },
              { key: 'subnets', label: 'SUBNETS' },
            ]}
          />
          <div className="subsection">
            <span className="eyebrow">SUBNET DIRECTORY</span>
            {state.subnets.map((x) => (
              <div className="mini-row" key={x.name}>
                <Wifi size={13} />
                <span>{x.name}</span>
                <small>{x.site || 'UNASSIGNED'}</small>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel title="REPLICATION PARTNERS" code="REPL">
        <Table
          rows={state.replication}
          rowKey="partner"
          cols={[
            { key: 'server', label: 'SERVER' },
            { key: 'partner', label: 'PARTNER' },
            { key: 'lastSuccess', label: 'LAST SUCCESS' },
            { key: 'failures', label: 'FAILURES' },
            {
              key: 'status',
              label: 'STATE',
              render: (v) => <Status ok={v === 'Healthy'}>{v}</Status>,
            },
          ]}
        />
      </Panel>
    </div>
  );
}
