import { useEffect, useState } from 'react';
import { Plus, RefreshCw, Trash2 } from 'lucide-react';
import { api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Status } from '../components/Status.jsx';
import { Modal } from '../components/Modal.jsx';
import { Table } from '../components/Table.jsx';
import { Panel } from '../components/Panel.jsx';
import { KV } from '../components/KV.jsx';

export function OUsPage({ notify, native = false }) {
  const [rows, setRows] = useState([]),
    [sel, setSel] = useState(null),
    [modal, setModal] = useState(null);
  const [loading, setLoading] = useState(true),
    [loadError, setLoadError] = useState('');
  async function load() {
    setLoading(true);
    setLoadError('');
    try {
      setRows(await api('/api/ad/ous'));
    } catch (e) {
      setLoadError(e.message);
      notify(e.message, 'bad');
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  async function create(v) {
    await api('/api/ad/ous', { method: 'POST', body: JSON.stringify(v) });
    notify('OU CREATED', 'ok');
    load();
  }
  async function del(v) {
    await api('/api/ad/ous/delete', {
      method: 'POST',
      body: JSON.stringify({ dn: sel.dn, recursive: v.recursive }),
    });
    notify('OU DELETED', 'ok');
    setSel(null);
    load();
  }
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
          title="ORGANIZATIONAL UNIT TREE"
          code="OU"
          actions={
            <>
              <Button
                perm="ou.write"
                icon={Plus}
                kind="primary"
                onClick={() => setModal('create')}
                disabled={native}
              >
                NEW OU
              </Button>
              <Button icon={RefreshCw} onClick={load}>
                REFRESH
              </Button>
            </>
          }
        >
          <Table
            rows={rows}
            rowKey="dn"
            selectedKey={sel?.dn}
            onRow={setSel}
            cols={[
              { key: 'name', label: 'OU' },
              { key: 'dn', label: 'DISTINGUISHED NAME' },
              {
                key: 'protected',
                label: 'PROTECTED',
                render: (v) => <Status ok={v}>{v == null ? 'UNKNOWN' : v ? 'YES' : 'NO'}</Status>,
              },
            ]}
          />
        </Panel>
        <Panel title="OU INSPECTOR" code="OBJ" className="inspector">
          {sel ? (
            <>
              <KV
                items={[
                  ['NAME', sel.name],
                  ['DN', sel.dn],
                  [
                    'ACCIDENTAL DELETE PROTECTION',
                    sel.protected == null
                      ? 'NOT READ BY LDAP CONNECTOR'
                      : sel.protected
                        ? 'ENABLED'
                        : 'DISABLED',
                  ],
                ]}
              />
              <Button
                perm="ou.write"
                icon={Trash2}
                kind="danger"
                onClick={() => setModal('delete')}
              >
                DELETE OU
              </Button>
            </>
          ) : (
            <div className="empty">SELECT AN OU</div>
          )}
        </Panel>
        {modal === 'create' && (
          <Modal
            title="CREATE ORGANIZATIONAL UNIT"
            fields={[
              { name: 'name', label: 'OU NAME' },
              { name: 'path', label: 'PARENT DN' },
              {
                name: 'protected',
                label: 'PROTECT FROM ACCIDENTAL DELETION',
                type: 'checkbox',
                default: true,
              },
            ]}
            onClose={() => setModal(null)}
            onSubmit={create}
          />
        )}
        {modal === 'delete' && sel && (
          <Modal
            title={'DELETE OU / ' + sel.name}
            subtitle="Recursive deletion will remove all child objects. Keep it off unless explicitly required."
            fields={[
              { name: 'recursive', label: 'RECURSIVE DELETE', type: 'checkbox', default: false },
            ]}
            danger
            submitLabel="DELETE OU"
            onClose={() => setModal(null)}
            onSubmit={del}
          />
        )}
      </div>
    </div>
  );
}
