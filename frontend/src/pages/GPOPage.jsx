import { useEffect, useState } from 'react';
import { Archive, KeyRound, Link2, Plus, RefreshCw, ShieldCheck, Trash2 } from 'lucide-react';
import { enc, api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Modal } from '../components/Modal.jsx';
import { Table } from '../components/Table.jsx';
import { Panel } from '../components/Panel.jsx';
import { KV } from '../components/KV.jsx';
import { useSession } from '../session.jsx';

export function GPOPage({ notify }) {
  const { can } = useSession();
  const [rows, setRows] = useState([]),
    [links, setLinks] = useState([]),
    [sel, setSel] = useState(null),
    [permissions, setPermissions] = useState([]),
    [modal, setModal] = useState(null),
    [report, setReport] = useState(null);
  async function load() {
    try {
      const [g, l] = await Promise.all([api('/api/gpo'), api('/api/gpo/links')]);
      setRows(g);
      setLinks(l);
    } catch (e) {
      notify(e.message, 'bad');
    }
  }
  async function open(r) {
    setSel(r);
    try {
      setPermissions(await api('/api/gpo/' + enc(r.id) + '/permissions'));
    } catch (e) {
      notify(e.message, 'bad');
    }
  }
  useEffect(() => {
    load();
  }, []);
  async function command(path, method = 'POST', body) {
    try {
      const r = await api(path, { method, body: body ? JSON.stringify(body) : undefined });
      notify('GPO COMMAND COMPLETED', 'ok');
      load();
      if (sel) open(sel);
      return r;
    } catch (e) {
      notify(e.message, 'bad');
      throw e;
    }
  }
  return (
    <div className="split">
      <Panel
        title="GROUP POLICY OBJECTS"
        code="GPO"
        actions={
          <>
            <Button perm="gpo.write" icon={Plus} kind="primary" onClick={() => setModal('create')}>
              NEW GPO
            </Button>
            <Button icon={RefreshCw} onClick={load}>
              REFRESH
            </Button>
          </>
        }
      >
        <Table
          rows={rows}
          rowKey="id"
          selectedKey={sel?.id}
          onRow={open}
          cols={[
            { key: 'displayName', label: 'GPO' },
            { key: 'status', label: 'STATUS' },
            { key: 'owner', label: 'OWNER' },
            { key: 'modified', label: 'MODIFIED' },
          ]}
        />
      </Panel>
      <Panel title="GPO INSPECTOR" code="OBJ" className="inspector">
        {!sel ? (
          <div className="empty">SELECT A POLICY OBJECT</div>
        ) : (
          <>
            <div className="object-head">
              <div className="avatar">
                <ShieldCheck />
              </div>
              <div>
                <h3>{sel.displayName}</h3>
                <p>{sel.id}</p>
              </div>
            </div>
            <KV
              items={[
                ['STATUS', sel.status],
                ['OWNER', sel.owner],
                ['MODIFIED', sel.modified],
              ]}
            />
            <div className="action-grid">
              <Button perm="gpo.write" icon={Link2} onClick={() => setModal('link')}>
                LINK
              </Button>
              <Button perm="gpo.write" icon={Archive} onClick={() => setModal('backup')}>
                BACKUP
              </Button>
              <Button perm="gpo.write" onClick={() => setModal('status')}>
                SET STATUS
              </Button>
              <Button
                onClick={async () => {
                  const r = await command('/api/gpo/' + enc(sel.id) + '/report', 'GET');
                  setReport(r);
                }}
              >
                REPORT
              </Button>
              <Button perm="gpo.write" icon={KeyRound} onClick={() => setModal('permission')}>
                SET ACL
              </Button>
              <Button
                perm="gpo.write"
                icon={Trash2}
                kind="danger"
                onClick={() => setModal('delete')}
              >
                DELETE
              </Button>
            </div>
            <div className="subsection">
              <span className="eyebrow">SECURITY FILTER / PERMISSIONS</span>
              {permissions.map((x, i) => (
                <div className="mini-row" key={i}>
                  <KeyRound size={13} />
                  <span>{x.trustee}</span>
                  <small>{x.permission}</small>
                </div>
              ))}
            </div>
            <div className="subsection">
              <span className="eyebrow">LINKS</span>
              {links
                .filter((x) => x.displayName === sel.displayName)
                .map((x, i) => (
                  <div className="mini-row" key={i}>
                    <Link2 size={13} />
                    <span>{x.target}</span>
                    <small>{x.enforced ? 'ENFORCED' : 'NORMAL'}</small>
                    <button
                      className="tiny-danger"
                      disabled={!can('gpo.write')}
                      onClick={() =>
                        command('/api/gpo/' + enc(sel.id) + '/unlink', 'POST', {
                          target: x.target,
                          enforced: false,
                          enabled: true,
                        })
                      }
                    >
                      UNLINK
                    </button>
                  </div>
                ))}
            </div>
          </>
        )}
      </Panel>
      {modal === 'create' && (
        <Modal
          title="CREATE GROUP POLICY OBJECT"
          fields={[
            { name: 'name', label: 'GPO NAME' },
            { name: 'comment', label: 'COMMENT' },
          ]}
          onClose={() => setModal(null)}
          onSubmit={(v) => command('/api/gpo', 'POST', v)}
        />
      )}
      {modal === 'link' && sel && (
        <Modal
          title={'LINK GPO / ' + sel.displayName}
          fields={[
            { name: 'target', label: 'TARGET DOMAIN / OU DN' },
            { name: 'enabled', label: 'LINK ENABLED', type: 'checkbox', default: true },
            { name: 'enforced', label: 'ENFORCED', type: 'checkbox', default: false },
            { name: 'order', label: 'LINK ORDER', type: 'number' },
          ]}
          onClose={() => setModal(null)}
          onSubmit={(v) => command('/api/gpo/' + enc(sel.id) + '/link', 'POST', v)}
        />
      )}
      {modal === 'permission' && sel && (
        <Modal
          title={'SET GPO PERMISSION / ' + sel.displayName}
          fields={[
            { name: 'trustee', label: 'USER / GROUP NAME' },
            {
              name: 'target_type',
              label: 'TARGET TYPE',
              type: 'select',
              options: ['User', 'Group', 'Computer'],
              default: 'Group',
            },
            {
              name: 'permission',
              label: 'PERMISSION',
              type: 'select',
              options: ['GpoRead', 'GpoApply', 'GpoEdit', 'GpoEditDeleteModifySecurity'],
              default: 'GpoRead',
            },
            {
              name: 'replace',
              label: 'REPLACE EXISTING PERMISSION',
              type: 'checkbox',
              default: false,
            },
          ]}
          onClose={() => setModal(null)}
          onSubmit={(v) => command('/api/gpo/' + enc(sel.id) + '/permissions', 'POST', v)}
        />
      )}
      {modal === 'backup' && sel && (
        <Modal
          title={'BACKUP GPO / ' + sel.displayName}
          fields={[
            {
              name: 'path',
              label: 'WINDOWS WORKER BACKUP PATH',
              default: 'C:\\ProgramData\\RsatFull\\GpoBackups',
            },
          ]}
          onClose={() => setModal(null)}
          onSubmit={(v) => command('/api/gpo/' + enc(sel.id) + '/backup', 'POST', v)}
        />
      )}
      {modal === 'status' && sel && (
        <Modal
          title={'SET GPO STATUS / ' + sel.displayName}
          fields={[
            {
              name: 'status',
              label: 'STATUS',
              type: 'select',
              options: [
                'AllSettingsEnabled',
                'UserSettingsDisabled',
                'ComputerSettingsDisabled',
                'AllSettingsDisabled',
              ],
              default: sel.status,
            },
          ]}
          onClose={() => setModal(null)}
          onSubmit={(v) => command('/api/gpo/' + enc(sel.id) + '/status', 'POST', v)}
        />
      )}
      {modal === 'delete' && sel && (
        <Modal
          title={'DELETE GPO / ' + sel.displayName}
          fields={[]}
          danger
          submitLabel="DELETE GPO"
          onClose={() => setModal(null)}
          onSubmit={() => command('/api/gpo/' + enc(sel.id), 'DELETE')}
        />
      )}
      {report && (
        <div className="modal-backdrop">
          <div className="modal report">
            <div className="modal-head">
              <div>
                <span className="eyebrow">GPO XML REPORT</span>
                <h3>{report.displayName}</h3>
              </div>
              <button className="x" onClick={() => setReport(null)}>
                ×
              </button>
            </div>
            <pre>{report.xml || JSON.stringify(report, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

export function NativeGPO({ notify }) {
  const [rows, setRows] = useState([]);
  async function load() {
    try {
      setRows(await api('/api/gpo'));
    } catch (e) {
      notify(e.message, 'bad');
    }
  }
  useEffect(() => {
    load();
  }, []);
  return (
    <Panel
      title="GROUP POLICY / AD INVENTORY"
      code="GPO"
      actions={
        <Button icon={RefreshCw} onClick={load}>
          REFRESH
        </Button>
      }
    >
      <div className="identity-model-note">
        <span>
          LDAP inventory only. GPO editing, permissions, links, backup and SYSVOL reports are
          unavailable.
        </span>
      </div>
      <Table
        rows={rows}
        rowKey="id"
        cols={[
          { key: 'displayName', label: 'NAME' },
          { key: 'id', label: 'GUID' },
          { key: 'status', label: 'STATUS' },
          { key: 'modified', label: 'MODIFIED' },
        ]}
      />
    </Panel>
  );
}
