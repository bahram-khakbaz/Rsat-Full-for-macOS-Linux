import { useEffect, useState } from 'react';
import { Archive, RefreshCw } from 'lucide-react';
import { api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Modal } from '../components/Modal.jsx';
import { Table } from '../components/Table.jsx';
import { Panel } from '../components/Panel.jsx';
import { KV } from '../components/KV.jsx';

export function RecyclePage({ notify }) {
  const [rows, setRows] = useState([]),
    [sel, setSel] = useState(null),
    [modal, setModal] = useState(null);
  async function load() {
    try {
      setRows(await api('/api/ad/deleted'));
    } catch (e) {
      notify(e.message, 'bad');
    }
  }
  useEffect(() => {
    load();
  }, []);
  async function restore(v) {
    await api('/api/ad/deleted/restore', {
      method: 'POST',
      body: JSON.stringify({ object_guid: sel.objectGuid, target_path: v.target_path || '' }),
    });
    notify('OBJECT RESTORED', 'ok');
    setSel(null);
    load();
  }
  return (
    <div className="split">
      <Panel
        title="ACTIVE DIRECTORY RECYCLE BIN"
        code="RCY"
        actions={
          <Button icon={RefreshCw} onClick={load}>
            REFRESH
          </Button>
        }
      >
        <Table
          rows={rows}
          rowKey="objectGuid"
          selectedKey={sel?.objectGuid}
          onRow={setSel}
          cols={[
            { key: 'name', label: 'DELETED OBJECT' },
            { key: 'objectClass', label: 'CLASS' },
            { key: 'lastKnownParent', label: 'LAST KNOWN PARENT' },
            { key: 'deletedAt', label: 'DELETED AT' },
          ]}
        />
      </Panel>
      <Panel title="RESTORE INSPECTOR" code="OBJ" className="inspector">
        {sel ? (
          <>
            <div className="object-head">
              <div className="avatar">
                <Archive />
              </div>
              <div>
                <h3>{sel.name}</h3>
                <p>{sel.objectGuid}</p>
              </div>
            </div>
            <KV
              items={[
                ['CLASS', sel.objectClass],
                ['LAST KNOWN PARENT', sel.lastKnownParent],
                ['DELETED AT', sel.deletedAt],
              ]}
            />
            <div className="action-grid">
              <Button
                perm="ad.update"
                icon={RefreshCw}
                kind="primary"
                onClick={() => setModal('restore')}
              >
                RESTORE OBJECT
              </Button>
            </div>
          </>
        ) : (
          <div className="empty">SELECT A DELETED OBJECT</div>
        )}
      </Panel>
      {modal === 'restore' && sel && (
        <Modal
          title={'RESTORE / ' + sel.name}
          subtitle="Leave target empty to restore to last known parent, or provide a different DN."
          fields={[{ name: 'target_path', label: 'OPTIONAL TARGET DN' }]}
          onClose={() => setModal(null)}
          onSubmit={restore}
        />
      )}
    </div>
  );
}
