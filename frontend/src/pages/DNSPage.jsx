import { useEffect, useState, useRef } from 'react';
import { Plus, RefreshCw, Search, Trash2 } from 'lucide-react';
import { enc, api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Modal } from '../components/Modal.jsx';
import { Table } from '../components/Table.jsx';
import { Panel } from '../components/Panel.jsx';
import { KV } from '../components/KV.jsx';
import { dnsRecordOwner } from '../dns-browser.mjs';
import DnsBrowser from '../components/DnsBrowser.jsx';

export function DNSPage({
  notify,
  dnsReadOnly = false,
  dnsZoneReadOnly = false,
  defaultZone = '',
}) {
  const readGeneration = useRef(0);
  const [query, setQuery] = useState(''),
    [folder, setFolder] = useState('');
  const [loadError, setLoadError] = useState(''),
    [loading, setLoading] = useState(false);
  const [zones, setZones] = useState([]),
    [zone, setZone] = useState(''),
    [records, setRecords] = useState([]),
    [sel, setSel] = useState(null),
    [modal, setModal] = useState(null);
  async function loadZones() {
    setLoading(true);
    try {
      const z = await api('/api/dns/zones');
      setZones(z);
      setLoadError('');
      if (!zone && z[0])
        setZone(
          z.find((x) => x.name.toLowerCase() === defaultZone.toLowerCase())?.name || z[0].name,
        );
      if (zone && !z.some((x) => x.name === zone)) setZone(z[0]?.name || '');
    } catch (e) {
      setLoadError(e.message);
      setZones([]);
    } finally {
      setLoading(false);
    }
  }
  async function loadRecords() {
    const generation = ++readGeneration.current;
    setLoading(true);
    try {
      const rows = await api('/api/dns/records' + (zone ? '?zone=' + enc(zone) : ''));
      if (generation === readGeneration.current) {
        setRecords(rows.map((r, i) => ({ ...r, id: i })));
        setSel(null);
        setLoadError('');
      }
    } catch (e) {
      if (generation === readGeneration.current) {
        setLoadError(e.message);
        setRecords([]);
      }
    } finally {
      if (generation === readGeneration.current) setLoading(false);
    }
  }
  useEffect(() => {
    loadZones().catch((e) => notify(e.message, 'bad'));
  }, []);
  useEffect(() => {
    setFolder('');
    setSel(null);
    if (zone) loadRecords();
    return () => {
      readGeneration.current++;
    };
  }, [zone]);
  function openFolder(path) {
    setFolder(path);
    setSel(null);
    setQuery('');
  }
  function chooseZone(value) {
    openFolder('');
    if (value !== zone) {
      readGeneration.current++;
      setRecords([]);
      setZone(value);
    }
  }
  async function create(v) {
    await api('/api/dns/records', {
      method: 'POST',
      body: JSON.stringify({
        ...v,
        zone,
        name: dnsRecordOwner(v.name, folder, zone),
        ttl: Number(v.ttl),
      }),
    });
    notify('DNS RECORD CREATED', 'ok');
    loadRecords();
  }
  async function edit(v) {
    await api('/api/dns/records/update', {
      method: 'POST',
      body: JSON.stringify({
        ...sel,
        value: v.value,
        ttl: Number(v.ttl),
        old_value: sel.value,
        old_ttl: sel.ttl,
      }),
    });
    notify('DNS RECORD UPDATED', 'ok');
    setSel(null);
    await loadRecords();
  }
  async function del() {
    await api('/api/dns/records/delete', { method: 'POST', body: JSON.stringify(sel) });
    notify('DNS RECORD REMOVED', 'ok');
    setSel(null);
    loadRecords();
  }
  async function createZone(v) {
    await api('/api/dns/zones', { method: 'POST', body: JSON.stringify(v) });
    notify('DNS ZONE CREATED', 'ok');
    await loadZones();
  }
  async function deleteZone() {
    await api('/api/dns/zones/delete', { method: 'POST', body: JSON.stringify({ name: zone }) });
    notify('DNS ZONE DELETED', 'ok');
    setSel(null);
    setZone('');
    await loadZones();
  }
  const z = zones.find((x) => x.name === zone);
  return (
    <div className="stack dns-page">
      {loading && <div className="directory-loading">READING DNS...</div>}
      {loadError && <div className="error-box">{loadError}</div>}
      <div className="split">
        <Panel
          title={'DNS RECORDS / ' + zone + ' / ' + records.length}
          code="DNS"
          actions={
            <>
              <div className="searchbox">
                <Search size={14} />
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search DNS name, value or type"
                />
              </div>
              <select
                className="toolbar-select"
                value={zone}
                aria-label="DNS zone"
                onChange={(e) => chooseZone(e.target.value)}
              >
                {zones.map((z) => (
                  <option key={z.name}>{z.name}</option>
                ))}
              </select>
              <Button
                perm="dns.write"
                icon={Plus}
                disabled={dnsReadOnly || dnsZoneReadOnly}
                onClick={() => setModal('zone')}
              >
                NEW ZONE
              </Button>
              <Button
                perm="dns.write"
                icon={Plus}
                kind="primary"
                disabled={!zone || dnsReadOnly || loading}
                onClick={() => setModal('create')}
              >
                NEW RECORD
              </Button>
              <Button
                perm="dns.write"
                disabled={
                  !sel ||
                  loading ||
                  dnsReadOnly ||
                  !['A', 'AAAA', 'CNAME', 'PTR', 'NS', 'MX', 'SRV', 'TXT'].includes(sel?.type)
                }
                onClick={() => setModal('edit')}
              >
                EDIT RECORD
              </Button>
              <Button
                perm="dns.write"
                icon={Trash2}
                kind="danger"
                disabled={
                  !sel ||
                  loading ||
                  dnsReadOnly ||
                  !['A', 'AAAA', 'CNAME', 'PTR', 'NS', 'MX', 'SRV', 'TXT'].includes(sel?.type)
                }
                onClick={() => setModal('delete')}
              >
                DELETE RECORD
              </Button>
              <Button
                icon={RefreshCw}
                onClick={async () => {
                  await loadZones();
                  if (zone) await loadRecords();
                }}
              >
                REFRESH
              </Button>
            </>
          }
        >
          <DnsBrowser
            records={records}
            zones={zones}
            zone={zone}
            folder={folder}
            onFolder={openFolder}
            onZone={chooseZone}
            query={query}
            selected={sel}
            onSelect={setSel}
            loading={loading}
            Table={Table}
            Button={Button}
          />
        </Panel>
        <Panel title="ZONE / RECORD INSPECTOR" code="OBJ" className="inspector">
          <KV
            items={[
              ['ZONE', zone],
              ['FOLDER', folder || '@ (zone root)'],
              ['ZONE TYPE', z?.type],
              ['AD INTEGRATED', z ? (z.integrated ? 'YES' : 'NO') : '—'],
              ['REVERSE LOOKUP', z?.reverse ? 'YES' : 'NO'],
            ]}
          />
          {zone && (
            <div className="action-grid">
              <Button
                perm="dns.write"
                icon={Trash2}
                kind="danger"
                disabled={dnsReadOnly || dnsZoneReadOnly}
                onClick={() => setModal('zoneDelete')}
              >
                DELETE ZONE
              </Button>
            </div>
          )}
          {!sel && <div className="empty">SELECT A RECORD TO EDIT OR DELETE</div>}
          {sel && (
            <>
              <div className="subsection">
                <KV
                  items={[
                    ['RECORD', sel.name],
                    ['TYPE', sel.type],
                    ['VALUE', sel.value],
                    ['TTL', sel.ttl],
                  ]}
                />
              </div>
            </>
          )}
        </Panel>
        {modal === 'zone' && (
          <Modal
            title="CREATE AD-INTEGRATED DNS ZONE"
            fields={[
              { name: 'name', label: 'ZONE NAME' },
              {
                name: 'replication_scope',
                label: 'REPLICATION SCOPE',
                type: 'select',
                options: ['Domain', 'Forest', 'Legacy'],
                default: 'Domain',
              },
              {
                name: 'dynamic_update',
                label: 'DYNAMIC UPDATE',
                type: 'select',
                options: ['Secure', 'NonsecureAndSecure', 'None'],
                default: 'Secure',
              },
            ]}
            onClose={() => setModal(null)}
            onSubmit={createZone}
          />
        )}
        {modal === 'zoneDelete' && zone && (
          <Modal
            title={'DELETE DNS ZONE / ' + zone}
            subtitle="This removes the entire DNS zone and all records in it."
            fields={[]}
            danger
            submitLabel="DELETE ZONE"
            onClose={() => setModal(null)}
            onSubmit={deleteZone}
          />
        )}
        {modal === 'create' && (
          <Modal
            title={'CREATE DNS RECORD / ' + [folder, zone].filter(Boolean).join('.')}
            subtitle={
              'NAME is relative to this folder; @ means the folder itself. MX: priority target · SRV: priority weight port target · TXT: quote each text segment, e.g. "text with spaces"'
            }
            initial={{ name: '@', type: 'A', ttl: 3600 }}
            fields={[
              { name: 'name', label: 'NAME IN THIS FOLDER (@ = PARENT)', required: true },
              {
                name: 'type',
                label: 'TYPE',
                type: 'select',
                options: ['A', 'AAAA', 'CNAME', 'PTR', 'NS', 'MX', 'SRV', 'TXT'],
                default: 'A',
              },
              { name: 'value', label: 'VALUE / TARGET' },
              { name: 'ttl', label: 'TTL SECONDS', type: 'number', default: 3600 },
            ]}
            onClose={() => setModal(null)}
            onSubmit={create}
          />
        )}
        {modal === 'edit' && sel && (
          <Modal
            title={'EDIT DNS RECORD / ' + sel.name}
            subtitle={
              sel.zone +
              ' · ' +
              sel.type +
              ' · MX: priority target; SRV: priority weight port target; TXT: quote text segments'
            }
            initial={{ value: sel.value, ttl: sel.ttl }}
            fields={[
              { name: 'value', label: 'VALUE / TARGET' },
              { name: 'ttl', label: 'TTL SECONDS', type: 'number' },
            ]}
            onClose={() => setModal(null)}
            onSubmit={edit}
          />
        )}
        {modal === 'delete' && sel && (
          <Modal
            title={'DELETE DNS RECORD / ' + sel.name}
            fields={[]}
            danger
            submitLabel="DELETE RECORD"
            onClose={() => setModal(null)}
            onSubmit={del}
          />
        )}
      </div>
    </div>
  );
}
