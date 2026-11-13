import { useEffect, useState } from 'react';
import { Pencil, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { useSession } from '../session.jsx';

const states = ['free', 'used', 'reserved', 'unknown'];

export default function IpamPanel({ api, ui }) {
  const { Panel, Button, Modal, Table } = ui;
  const [vlans, setVlans] = useState([]),
    [chosen, setChosen] = useState(null);
  const [onlyFree, setOnlyFree] = useState(true),
    [busy, setBusy] = useState(false);
  const [error, setError] = useState(''),
    [loaded, setLoaded] = useState(false),
    [adding, setAdding] = useState(false),
    [dialog, setDialog] = useState(null);
  const { can } = useSession();
  const writable = can('ipam.write');
  const selected = vlans.find((v) => v.id === chosen) || vlans[0];

  async function load() {
    setBusy(true);
    try {
      setVlans(await api('/api/ipam/vlans'));
      setError('');
      setLoaded(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function change(ip, status) {
    setBusy(true);
    setError('');
    try {
      const updated = await api(`/api/ipam/vlans/${selected.id}/addresses/${ip}`, {
        method: 'PATCH',
        body: JSON.stringify({ status, revision: selected.revision }),
      });
      setVlans((previous) => previous.map((v) => (v.id === updated.id ? updated : v)));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="VLAN / IP ADDRESS MANAGEMENT"
      code="IPAM"
      className="ipam-panel"
      actions={
        <>
          <Button perm="ipam.write" icon={Plus} disabled={busy} onClick={() => setAdding(true)}>
            ADD VLAN
          </Button>
          <Button icon={RefreshCw} disabled={busy} onClick={load}>
            REFRESH IP LIST
          </Button>
        </>
      }
    >
      <div className="identity-model-note">
        <span>
          Manual allocation list stored locally. FREE means marked available, not verified by a
          network scan. Network and broadcast addresses are excluded; reserve gateways explicitly.
          Checking an IP marks it USED and removes it from the free-only view.
        </span>
      </div>
      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}
      <div className="ipam-networks">
        {vlans.map((v) => (
          <button
            key={v.id}
            disabled={busy}
            aria-pressed={selected?.id === v.id}
            className={'ipam-network ' + (selected?.id === v.id ? 'active' : '')}
            onClick={() => setChosen(v.id)}
          >
            <strong>{v.name}</strong>
            <code>{v.cidr}</code>
            <span className="ipam-counts">
              {states.map((state) => (
                <span key={state} className={'ipam-' + state}>
                  {state.toUpperCase()}: {v.counts[state]}
                </span>
              ))}
            </span>
            <small>USABLE: {v.total}</small>
          </button>
        ))}
      </div>
      {!selected && (
        <div className="empty">{loaded ? 'NO VLANS ADDED' : 'LOADING VLAN INVENTORY...'}</div>
      )}
      {selected && (
        <>
          <div className="inline-tools ipam-filter">
            <label>
              <input
                type="checkbox"
                checked={onlyFree}
                onChange={(e) => setOnlyFree(e.target.checked)}
              />{' '}
              ONLY FREE IPs / فقط IPهای آزاد
            </label>
            <Button
              icon={Pencil}
              perm="ipam.write"
              disabled={busy}
              onClick={() => setDialog('edit')}
            >
              EDIT VLAN
            </Button>
            <Button
              icon={Trash2}
              kind="danger"
              perm="ipam.write"
              disabled={busy}
              onClick={() => setDialog('delete')}
            >
              DELETE VLAN
            </Button>
            <span>
              {selected.name} · {selected.cidr} · {selected.counts.free} FREE /{' '}
              {selected.counts.used} USED / {selected.counts.reserved} RESERVED /{' '}
              {selected.counts.unknown} UNKNOWN
            </span>
          </div>
          <Table
            rows={selected.addresses.filter((a) => !onlyFree || a.status === 'free')}
            rowKey="ip"
            empty={onlyFree ? 'NO FREE IPs IN THIS VLAN' : 'NO HOST ADDRESSES'}
            cols={[
              {
                key: 'allocated',
                label: 'USED ✓',
                render: (_, row) => (
                  <input
                    type="checkbox"
                    aria-label={'Mark ' + row.ip + ' as used'}
                    checked={row.status === 'used'}
                    disabled={busy || !writable || row.status === 'reserved'}
                    onChange={(e) => change(row.ip, e.target.checked ? 'used' : 'free')}
                  />
                ),
              },
              { key: 'ip', label: 'IP ADDRESS' },
              {
                key: 'status',
                label: 'ALLOCATION',
                render: (value, row) => (
                  <select
                    aria-label={'Allocation for ' + row.ip}
                    value={value}
                    disabled={busy || !writable}
                    onChange={(e) => change(row.ip, e.target.value)}
                  >
                    {states.map((state) => (
                      <option key={state} value={state}>
                        {state.toUpperCase()}
                      </option>
                    ))}
                  </select>
                ),
              },
            ]}
          />
          <div className="ipam-boundaries">
            Network: {selected.network} · Broadcast: {selected.broadcast} · Changes save
            immediately; use REFRESH IP LIST if another window changed the inventory.
          </div>
        </>
      )}
      {dialog === 'edit' && selected && (
        <Modal
          title={'EDIT VLAN / ' + selected.cidr}
          subtitle="The subnet itself cannot be changed. The default status applies to addresses that were never set explicitly."
          initial={{ name: selected.name, default_status: selected.default_status || '' }}
          fields={[
            { name: 'name', label: 'VLAN NAME', required: true, maxLength: 120 },
            {
              name: 'default_status',
              label: 'DEFAULT HOST STATUS',
              type: 'select',
              // Never guess the stored default: an empty choice is sent as "not provided".
              options: (selected.default_status ? [] : ['']).concat(states),
            },
          ]}
          submitLabel="SAVE VLAN"
          onClose={() => setDialog(null)}
          onSubmit={async (values) => {
            // A stale revision is rejected with 409; the message is shown in this dialog.
            const updated = await api('/api/ipam/vlans/' + selected.id, {
              method: 'PUT',
              body: JSON.stringify({
                name: values.name,
                default_status: values.default_status || undefined,
                revision: selected.revision,
              }),
            });
            setVlans((previous) => previous.map((v) => (v.id === updated.id ? updated : v)));
          }}
        />
      )}
      {dialog === 'delete' && selected && (
        <Modal
          title={'DELETE VLAN / ' + selected.name + ' ?'}
          subtitle={
            selected.cidr +
            ' and all of its allocation marks are removed from this local list. No network device is changed. This cannot be undone.'
          }
          fields={[]}
          danger
          submitLabel="DELETE VLAN"
          onClose={() => setDialog(null)}
          onSubmit={async () => {
            await api('/api/ipam/vlans/' + selected.id, { method: 'DELETE' });
            setVlans((previous) => previous.filter((v) => v.id !== selected.id));
            setChosen(null);
          }}
        />
      )}
      {adding && (
        <Modal
          title="ADD VLAN / IPv4 SUBNET"
          subtitle="Creates a local allocation list only. No DHCP, DNS, switch or server configuration is changed."
          fields={[
            { name: 'name', label: 'VLAN NAME', required: true },
            { name: 'cidr', label: 'IPv4 CIDR (e.g. 192.0.2.0/28)', required: true },
            {
              name: 'default_status',
              label: 'INITIAL HOST STATUS',
              type: 'select',
              options: ['unknown', 'free', 'used', 'reserved'],
              default: 'unknown',
            },
          ]}
          submitLabel="SAVE VLAN"
          onClose={() => setAdding(false)}
          onSubmit={async (values) => {
            const created = await api('/api/ipam/vlans', {
              method: 'POST',
              body: JSON.stringify(values),
            });
            setVlans((previous) => [...previous, created]);
            setChosen(created.id);
          }}
        />
      )}
    </Panel>
  );
}
