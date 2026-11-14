import { useEffect, useState } from 'react';
import { Group, Plus, RefreshCw, Search, Trash2, Users } from 'lucide-react';
import { enc, api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Modal } from '../components/Modal.jsx';
import { Table } from '../components/Table.jsx';
import { Panel } from '../components/Panel.jsx';
import { useSession } from '../session.jsx';

export function GroupsPage({ notify }) {
  const [rows, setRows] = useState([]),
    [sel, setSel] = useState(null),
    [members, setMembers] = useState([]),
    [modal, setModal] = useState(null),
    [q, setQ] = useState('');
  const { can } = useSession();
  const [loading, setLoading] = useState(true),
    [loadError, setLoadError] = useState('');
  async function load(query = q) {
    if (typeof query !== 'string') query = q;
    setLoading(true);
    setLoadError('');
    try {
      const search = query.trim() ? '?' + new URLSearchParams({ q: query.trim() }) : '';
      setRows(await api('/api/ad/groups' + search));
    } catch (e) {
      setLoadError(e.message);
      notify(e.message, 'bad');
    } finally {
      setLoading(false);
    }
  }
  async function open(r) {
    setSel(r);
    try {
      setMembers(await api('/api/ad/groups/' + enc(r.name) + '/members'));
    } catch (e) {
      notify(e.message, 'bad');
    }
  }
  async function command(path, method = 'POST', body) {
    try {
      await api(path, { method, body: body ? JSON.stringify(body) : undefined });
      notify('GROUP COMMAND COMPLETED', 'ok');
      load();
      if (sel) open(sel);
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
          title="SECURITY / DISTRIBUTION GROUPS"
          code="GRP"
          actions={
            <>
              <div className="searchbox">
                <Search size={14} />
                <input
                  value={q}
                  aria-label="Search groups by name prefix"
                  onChange={(e) => setQ(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && load()}
                  placeholder="group name prefix"
                />
              </div>
              <Button
                perm="group.write"
                icon={Plus}
                kind="primary"
                onClick={() => setModal('create')}
              >
                NEW GROUP
              </Button>
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
            onRow={open}
            cols={[
              { key: 'name', label: 'GROUP' },
              { key: 'category', label: 'CATEGORY' },
              { key: 'scope', label: 'SCOPE' },
              { key: 'members', label: 'MEMBERS' },
            ]}
          />
        </Panel>
        <Panel title="MEMBERSHIP INSPECTOR" code="MBR" className="inspector">
          {!sel ? (
            <div className="empty">SELECT A GROUP</div>
          ) : (
            <>
              <div className="object-head">
                <div className="avatar">
                  <Group />
                </div>
                <div>
                  <h3>{sel.name}</h3>
                  <p>{sel.description || 'NO DESCRIPTION'}</p>
                </div>
              </div>
              <div className="panel-actions left">
                <Button perm="group.membership" icon={Plus} onClick={() => setModal('add')}>
                  ADD MEMBER
                </Button>
                <Button
                  perm="group.write"
                  icon={Trash2}
                  kind="danger"
                  onClick={() => setModal('delete')}
                >
                  DELETE GROUP
                </Button>
              </div>
              <div className="subsection">
                {members.map((m) => (
                  <div className="mini-row" key={m.dn || m.samAccountName}>
                    <Users size={13} />
                    <span>{m.name}</span>
                    <small>{m.objectClass}</small>
                    <button
                      className="tiny-danger"
                      disabled={!can('group.membership')}
                      onClick={() =>
                        command(
                          '/api/ad/groups/' +
                            enc(sel.name) +
                            '/members/' +
                            enc(m.samAccountName || m.dn),
                          'DELETE',
                        )
                      }
                    >
                      REMOVE
                    </button>
                  </div>
                ))}
              </div>
            </>
          )}
        </Panel>
        {modal === 'create' && (
          <Modal
            title="CREATE GROUP"
            fields={[
              { name: 'name', label: 'GROUP NAME' },
              {
                name: 'scope',
                label: 'SCOPE',
                type: 'select',
                options: ['Global', 'DomainLocal', 'Universal'],
                default: 'Global',
              },
              {
                name: 'category',
                label: 'CATEGORY',
                type: 'select',
                options: ['Security', 'Distribution'],
                default: 'Security',
              },
              { name: 'path', label: 'TARGET OU DN' },
              { name: 'description', label: 'DESCRIPTION' },
            ]}
            onClose={() => setModal(null)}
            onSubmit={async (v) => {
              await api('/api/ad/groups', { method: 'POST', body: JSON.stringify(v) });
              notify('GROUP CREATED', 'ok');
              load();
            }}
          />
        )}
        {modal === 'add' && sel && (
          <Modal
            title={'ADD MEMBER / ' + sel.name}
            fields={[{ name: 'member', label: 'USER OR OBJECT IDENTITY' }]}
            onClose={() => setModal(null)}
            onSubmit={(v) => command('/api/ad/groups/' + enc(sel.name) + '/members', 'POST', v)}
          />
        )}
        {modal === 'delete' && sel && (
          <Modal
            title={'DELETE GROUP / ' + sel.name}
            fields={[]}
            danger
            submitLabel="DELETE GROUP"
            onClose={() => setModal(null)}
            onSubmit={() => command('/api/ad/groups/' + enc(sel.name), 'DELETE')}
          />
        )}
      </div>
    </div>
  );
}
