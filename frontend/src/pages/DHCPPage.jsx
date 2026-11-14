import { useEffect, useState, useRef } from 'react';
import { Plus, RefreshCw, Trash2 } from 'lucide-react';
import { enc, api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Modal } from '../components/Modal.jsx';
import { Table } from '../components/Table.jsx';
import { Panel } from '../components/Panel.jsx';

export function DHCPPage({ notify }) {
  const readGeneration = useRef(0);
  const [loadError, setLoadError] = useState(''),
    [loading, setLoading] = useState(false);
  const [scopes, setScopes] = useState([]),
    [scope, setScope] = useState(''),
    [leases, setLeases] = useState([]),
    [reservations, setReservations] = useState([]),
    [tab, setTab] = useState('leases'),
    [sel, setSel] = useState(null),
    [modal, setModal] = useState(null);
  async function loadScopes() {
    setLoading(true);
    try {
      const s = await api('/api/dhcp/scopes');
      setScopes(s);
      setLoadError('');
      if (!scope && s[0]) setScope(s[0].scopeId);
      if (scope && !s.some((x) => x.scopeId === scope)) setScope(s[0]?.scopeId || '');
    } catch (e) {
      setLoadError(e.message);
      setScopes([]);
    } finally {
      setLoading(false);
    }
  }
  async function loadData() {
    const generation = ++readGeneration.current;
    if (!scope) return;
    try {
      const [l, r] = await Promise.all([
        api('/api/dhcp/leases?scope_id=' + enc(scope)),
        api('/api/dhcp/reservations?scope_id=' + enc(scope)),
      ]);
      if (generation === readGeneration.current) {
        setLeases(l);
        setReservations(r);
        setLoadError('');
      }
    } catch (e) {
      if (generation === readGeneration.current) {
        setLeases([]);
        setReservations([]);
        setLoadError(e.message);
      }
    }
  }
  useEffect(() => {
    loadScopes().catch((e) => notify(e.message, 'bad'));
  }, []);
  useEffect(() => {
    setSel(null);
    setLeases([]);
    setReservations([]);
    loadData();
  }, [scope]);
  async function create(v) {
    await api('/api/dhcp/reservations', { method: 'POST', body: JSON.stringify(v) });
    notify('RESERVATION CREATED', 'ok');
    loadData();
  }
  async function del() {
    await api('/api/dhcp/reservations/delete', {
      method: 'POST',
      body: JSON.stringify({ scope_id: sel.scopeId, ip_address: sel.ipAddress }),
    });
    notify('RESERVATION REMOVED', 'ok');
    setSel(null);
    loadData();
  }
  async function createScope(v) {
    await api('/api/dhcp/scopes', { method: 'POST', body: JSON.stringify(v) });
    notify('DHCP SCOPE CREATED', 'ok');
    await loadScopes();
  }
  async function scopeState(state) {
    await api('/api/dhcp/scopes/state', {
      method: 'POST',
      body: JSON.stringify({ scope_id: scope, state }),
    });
    notify('SCOPE STATE UPDATED', 'ok');
    await loadScopes();
  }
  async function deleteScope() {
    await api('/api/dhcp/scopes/delete', {
      method: 'POST',
      body: JSON.stringify({ scope_id: scope }),
    });
    notify('DHCP SCOPE DELETED', 'ok');
    setScope('');
    await loadScopes();
  }
  const s = scopes.find((x) => x.scopeId === scope);
  return (
    <div className="stack">
      {loading && <div className="directory-loading">READING DHCP...</div>}
      {loadError && <div className="error-box">{loadError}</div>}
      <Panel
        title="DHCP SCOPE SELECTOR"
        code="DHC"
        actions={
          <>
            <select
              className="toolbar-select"
              value={scope}
              onChange={(e) => {
                readGeneration.current++;
                setSel(null);
                setLeases([]);
                setReservations([]);
                setScope(e.target.value);
              }}
            >
              {scopes.map((x) => (
                <option key={x.scopeId} value={x.scopeId}>
                  {x.scopeId} / {x.name}
                </option>
              ))}
            </select>
            <Button
              perm="dhcp.write"
              icon={Plus}
              kind="primary"
              onClick={() => setModal('scopeCreate')}
            >
              NEW SCOPE
            </Button>
            {s && (
              <Button
                perm="dhcp.write"
                onClick={() => scopeState(s.state === 'Active' ? 'Inactive' : 'Active')}
              >
                {s.state === 'Active' ? 'DEACTIVATE' : 'ACTIVATE'}
              </Button>
            )}
            {s && (
              <Button
                perm="dhcp.write"
                icon={Trash2}
                kind="danger"
                onClick={() => setModal('scopeDelete')}
              >
                DELETE SCOPE
              </Button>
            )}
            <Button
              icon={RefreshCw}
              onClick={async () => {
                await loadScopes();
                await loadData();
              }}
            >
              REFRESH
            </Button>
          </>
        }
      >
        <div className="metrics compact">
          {s &&
            [
              ['STATE', s.state, 'STA'],
              ['RANGE', s.startRange + ' — ' + s.endRange, 'RNG'],
              ['IN USE', s.inUse, 'USE'],
              ['FREE', s.free, 'FRE'],
            ].map((x) => (
              <div className="metric" key={x[0]}>
                <span>{x[2]}</span>
                <strong>{x[1] ?? '—'}</strong>
                <small>{x[0]}</small>
              </div>
            ))}
        </div>
      </Panel>
      <Panel
        title="ADDRESS ALLOCATION"
        code="ADDR"
        actions={
          <>
            <Button
              kind={tab === 'leases' ? 'active' : ''}
              onClick={() => {
                setTab('leases');
                setSel(null);
              }}
            >
              LEASES
            </Button>
            <Button
              kind={tab === 'reservations' ? 'active' : ''}
              onClick={() => {
                setTab('reservations');
                setSel(null);
              }}
            >
              RESERVATIONS
            </Button>
            {tab === 'reservations' && (
              <Button
                perm="dhcp.write"
                icon={Plus}
                kind="primary"
                onClick={() => setModal('create')}
              >
                NEW RESERVATION
              </Button>
            )}
          </>
        }
      >
        {tab === 'leases' ? (
          <Table
            rows={leases}
            rowKey="ipAddress"
            cols={[
              { key: 'ipAddress', label: 'IP ADDRESS' },
              { key: 'hostName', label: 'HOSTNAME' },
              { key: 'clientId', label: 'CLIENT ID' },
              { key: 'state', label: 'STATE' },
              { key: 'expiry', label: 'EXPIRY' },
            ]}
          />
        ) : (
          <Table
            rows={reservations}
            rowKey="ipAddress"
            selectedKey={sel?.ipAddress}
            onRow={setSel}
            cols={[
              { key: 'ipAddress', label: 'IP ADDRESS' },
              { key: 'name', label: 'NAME' },
              { key: 'clientId', label: 'CLIENT ID' },
              { key: 'description', label: 'DESCRIPTION' },
            ]}
          />
        )}
        {tab === 'reservations' && sel && (
          <div className="inline-tools">
            <Button
              perm="dhcp.write"
              icon={Trash2}
              kind="danger"
              onClick={() => setModal('delete')}
            >
              DELETE SELECTED RESERVATION
            </Button>
          </div>
        )}
      </Panel>
      {modal === 'scopeCreate' && (
        <Modal
          title="CREATE DHCP IPV4 SCOPE"
          fields={[
            { name: 'name', label: 'SCOPE NAME' },
            { name: 'start_range', label: 'START RANGE' },
            { name: 'end_range', label: 'END RANGE' },
            { name: 'subnet_mask', label: 'SUBNET MASK' },
            { name: 'lease_days', label: 'LEASE DAYS', type: 'number', default: 8 },
            {
              name: 'state',
              label: 'INITIAL STATE',
              type: 'select',
              options: ['Active', 'Inactive'],
              default: 'Active',
            },
            { name: 'description', label: 'DESCRIPTION' },
          ]}
          onClose={() => setModal(null)}
          onSubmit={createScope}
        />
      )}
      {modal === 'scopeDelete' && s && (
        <Modal
          title={'DELETE DHCP SCOPE / ' + scope}
          subtitle="All leases, reservations and scope settings will be removed."
          fields={[]}
          danger
          submitLabel="DELETE SCOPE"
          onClose={() => setModal(null)}
          onSubmit={deleteScope}
        />
      )}
      {modal === 'create' && (
        <Modal
          title={'CREATE DHCP RESERVATION / ' + scope}
          initial={{ scope_id: scope }}
          fields={[
            { name: 'scope_id', label: 'SCOPE ID' },
            { name: 'ip_address', label: 'IP ADDRESS' },
            { name: 'client_id', label: 'CLIENT ID / MAC' },
            { name: 'name', label: 'NAME' },
            { name: 'description', label: 'DESCRIPTION' },
          ]}
          onClose={() => setModal(null)}
          onSubmit={create}
        />
      )}
      {modal === 'delete' && sel && (
        <Modal
          title={'DELETE RESERVATION / ' + sel.ipAddress}
          fields={[]}
          danger
          submitLabel="DELETE RESERVATION"
          onClose={() => setModal(null)}
          onSubmit={del}
        />
      )}
    </div>
  );
}
