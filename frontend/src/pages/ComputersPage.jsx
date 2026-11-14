import { useEffect, useState } from 'react';
import { Computer, FolderTree, RefreshCw, Search, Trash2 } from 'lucide-react';
import { enc, api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Status } from '../components/Status.jsx';
import { Modal } from '../components/Modal.jsx';
import { Table } from '../components/Table.jsx';
import { Panel } from '../components/Panel.jsx';
import { KV } from '../components/KV.jsx';

export function ComputersPage({ notify, native = false }) {
  const [rows, setRows] = useState([]),
    [q, setQ] = useState(''),
    [sel, setSel] = useState(null),
    [modal, setModal] = useState(null);
  const [loading, setLoading] = useState(true),
    [loadError, setLoadError] = useState('');
  async function load() {
    setLoading(true);
    setLoadError('');
    try {
      setRows(await api('/api/ad/computers' + (q ? '?q=' + enc(q) : '')));
    } catch (e) {
      setLoadError(e.message);
      notify(e.message, 'bad');
    } finally {
      setLoading(false);
    }
  }
  async function command(path, method = 'POST', body) {
    try {
      await api(path, { method, body: body ? JSON.stringify(body) : undefined });
      notify('COMPUTER COMMAND COMPLETED', 'ok');
      load();
    } catch (e) {
      notify(e.message, 'bad');
    }
  }
  useEffect(() => {
    load();
  }, []);
  return (
    <div className="stack">
      {loading && <div className="directory-loading">READING ACTIVE DIRECTORY...</div>}
      {loadError && (
        <div className="error-box" role="alert">
          {loadError}
        </div>
      )}
      <div className="split">
        <Panel
          title="DOMAIN COMPUTERS"
          code="CMP"
          actions={
            <>
              <div className="searchbox">
                <Search size={14} />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && load()}
                  placeholder="hostname"
                />
              </div>
              <Button icon={RefreshCw} onClick={load}>
                REFRESH
              </Button>
            </>
          }
        >
          <Table
            rows={rows}
            rowKey="name"
            selectedKey={sel?.name}
            onRow={setSel}
            cols={[
              { key: 'name', label: 'HOSTNAME' },
              { key: 'os', label: 'OPERATING SYSTEM' },
              { key: 'ipv4', label: 'IPV4' },
              {
                key: 'enabled',
                label: 'STATE',
                render: (v) => <Status ok={v}>{v ? 'ENABLED' : 'DISABLED'}</Status>,
              },
              { key: 'lastLogon', label: 'LAST LOGON' },
            ]}
          />
        </Panel>
        <Panel title="COMPUTER OBJECT" code="OBJ" className="inspector">
          {!sel ? (
            <div className="empty">SELECT A COMPUTER</div>
          ) : (
            <>
              <div className="object-head">
                <div className="avatar">
                  <Computer />
                </div>
                <div>
                  <h3>{sel.name}</h3>
                  <p>{sel.os}</p>
                </div>
              </div>
              <KV
                items={[
                  ['IPV4', sel.ipv4],
                  ['LAST LOGON', sel.lastLogon],
                  ['OU', sel.ou],
                  ['STATE', sel.enabled ? 'ENABLED' : 'DISABLED'],
                ]}
              />
              <div className="action-grid">
                <Button
                  perm="computer.write"
                  onClick={() =>
                    command(
                      '/api/ad/computers/' +
                        enc(sel.name) +
                        '/' +
                        (sel.enabled ? 'disable' : 'enable'),
                    )
                  }
                >
                  {sel.enabled ? 'DISABLE' : 'ENABLE'}
                </Button>
                <Button
                  perm="computer.write"
                  icon={RefreshCw}
                  onClick={() => setModal('reset')}
                  disabled={native}
                >
                  RESET ACCOUNT
                </Button>
                <Button perm="computer.write" icon={FolderTree} onClick={() => setModal('move')}>
                  MOVE OU
                </Button>
                <Button
                  perm="computer.delete"
                  icon={Trash2}
                  kind="danger"
                  onClick={() => setModal('delete')}
                >
                  DELETE
                </Button>
              </div>
            </>
          )}
        </Panel>
        {modal === 'move' && sel && (
          <Modal
            title={'MOVE ' + sel.name}
            fields={[{ name: 'target_ou', label: 'TARGET OU DN' }]}
            onClose={() => setModal(null)}
            onSubmit={(v) => command('/api/ad/computers/' + enc(sel.name) + '/move', 'POST', v)}
          />
        )}
        {modal === 'reset' && sel && (
          <Modal
            title={'RESET COMPUTER ACCOUNT / ' + sel.name}
            subtitle="The workstation may need its secure channel repaired or to be rejoined."
            fields={[]}
            submitLabel="RESET ACCOUNT"
            onClose={() => setModal(null)}
            onSubmit={() => command('/api/ad/computers/' + enc(sel.name) + '/reset')}
          />
        )}
        {modal === 'delete' && sel && (
          <Modal
            title={'DELETE COMPUTER / ' + sel.name}
            fields={[]}
            danger
            submitLabel="DELETE OBJECT"
            onClose={() => setModal(null)}
            onSubmit={() => command('/api/ad/computers/' + enc(sel.name), 'DELETE')}
          />
        )}
      </div>
    </div>
  );
}
