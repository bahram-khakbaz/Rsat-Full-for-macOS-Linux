import { useEffect, useState } from 'react';
import { KeyRound, Plus, RefreshCw, Trash2, UnlockKeyhole, UserRoundCog } from 'lucide-react';
import { api } from '../api.js';
import { MIN_PANEL_PASSWORD } from '../constants.js';
import { useSession } from '../session.jsx';
import { Button } from './Button.jsx';
import { Modal } from './Modal.jsx';
import { Panel } from './Panel.jsx';
import { Status } from './Status.jsx';
import { Table } from './Table.jsx';

const when = (value) => (value ? new Date(value).toLocaleString() : '—');
const passwordField = (label) => ({
  name: 'password',
  label: label + ' (' + MIN_PANEL_PASSWORD + '+ CHARACTERS)',
  type: 'password',
  minLength: MIN_PANEL_PASSWORD,
  required: true,
});

/** Panel sign-in accounts and their roles. Separate from AD and SSH identities. */
export function OperatorsPanel({ notify }) {
  const { me } = useSession();
  const [rows, setRows] = useState([]),
    [roles, setRoles] = useState({}),
    [selectedId, setSelectedId] = useState(null),
    [modal, setModal] = useState(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState('');
  const selected = rows.find((row) => row.id === selectedId) || null;
  const roleNames = Object.keys(roles);
  const isSelf = selected?.username === me?.username;

  async function load() {
    setLoading(true);
    try {
      const [operators, roleMap] = await Promise.all([
        api('/api/operators'),
        api('/api/operators/roles'),
      ]);
      setRows(operators);
      setRoles(roleMap || {});
      setError('');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);

  async function patch(body, message) {
    await api('/api/operators/' + selected.id, { method: 'PATCH', body: JSON.stringify(body) });
    notify(message, 'ok');
    await load();
  }
  async function run(action) {
    try {
      await action();
    } catch (e) {
      notify(e.message, 'bad');
    }
  }

  return (
    <Panel
      title={'PANEL OPERATORS / ' + rows.length}
      code="OPS"
      className="operators-panel"
      actions={
        <>
          <Button icon={Plus} kind="primary" onClick={() => setModal('create')}>
            ADD OPERATOR
          </Button>
          <Button icon={RefreshCw} disabled={loading} onClick={load}>
            REFRESH
          </Button>
        </>
      }
    >
      <div className="identity-model-note">
        <span>
          Operators sign in to this panel only; each role limits which modules and actions are
          offered and enforced by the API. Directory and SSH credentials are configured separately.
          The administrator defined by the server environment is managed in the deployment
          configuration, not here.
        </span>
      </div>
      {error && (
        <div className="error-box" role="alert">
          {error}
        </div>
      )}
      <Table
        rows={rows}
        rowKey="id"
        selectedKey={selectedId}
        onRow={(row) => setSelectedId(row.id)}
        empty={loading ? 'LOADING OPERATORS...' : 'NO LOCAL OPERATORS'}
        cols={[
          { key: 'username', label: 'OPERATOR' },
          { key: 'role', label: 'ROLE' },
          {
            key: 'disabled',
            label: 'STATE',
            render: (_, row) => (
              <Status ok={row.disabled ? false : row.locked ? null : true}>
                {row.disabled ? 'DISABLED' : row.locked ? 'LOCKED' : 'ACTIVE'}
              </Status>
            ),
          },
          { key: 'created_at', label: 'CREATED', render: when },
          { key: 'last_login_at', label: 'LAST SIGN-IN', render: when },
        ]}
      />
      {selected && (
        <>
          <div className="inline-tools">
            <span>
              {selected.username} · {(roles[selected.role] || []).join(', ') || 'no permissions'}
            </span>
            <Button icon={UserRoundCog} disabled={isSelf} onClick={() => setModal('role')}>
              CHANGE ROLE
            </Button>
            <Button icon={KeyRound} onClick={() => setModal('password')}>
              RESET PASSWORD
            </Button>
            {selected.locked && (
              <Button
                icon={UnlockKeyhole}
                onClick={() =>
                  run(async () => {
                    await api('/api/operators/' + selected.id + '/unlock', { method: 'POST' });
                    notify('OPERATOR UNLOCKED', 'ok');
                    await load();
                  })
                }
              >
                UNLOCK
              </Button>
            )}
            <Button
              disabled={isSelf}
              onClick={() =>
                run(() =>
                  patch(
                    { disabled: !selected.disabled },
                    selected.disabled ? 'OPERATOR ENABLED' : 'OPERATOR DISABLED',
                  ),
                )
              }
            >
              {selected.disabled ? 'ENABLE' : 'DISABLE'}
            </Button>
            <Button
              icon={Trash2}
              kind="danger"
              disabled={isSelf}
              onClick={() => setModal('delete')}
            >
              DELETE
            </Button>
          </div>
          {isSelf && (
            <small>
              You cannot change your own role, disable or delete your own account. Use My account
              for your password.
            </small>
          )}
        </>
      )}
      {modal === 'create' && (
        <Modal
          title="ADD PANEL OPERATOR"
          subtitle="Share the initial password over a trusted channel and ask the operator to change it under My account."
          fields={[
            { name: 'username', label: 'USERNAME', required: true, maxLength: 64 },
            passwordField('INITIAL PASSWORD'),
            {
              name: 'role',
              label: 'ROLE',
              type: 'select',
              options: roleNames,
              default: roleNames.includes('read_only') ? 'read_only' : roleNames[0],
            },
          ]}
          submitLabel="CREATE OPERATOR"
          onClose={() => setModal(null)}
          onSubmit={async (values) => {
            const created = await api('/api/operators', {
              method: 'POST',
              body: JSON.stringify(values),
            });
            notify('OPERATOR CREATED', 'ok');
            await load();
            if (created?.id != null) setSelectedId(created.id);
          }}
        />
      )}
      {modal === 'role' && selected && (
        <Modal
          title={'CHANGE ROLE / ' + selected.username}
          initial={{ role: selected.role }}
          fields={[{ name: 'role', label: 'ROLE', type: 'select', options: roleNames }]}
          submitLabel="SAVE ROLE"
          onClose={() => setModal(null)}
          onSubmit={(values) => patch({ role: values.role }, 'OPERATOR ROLE UPDATED')}
        />
      )}
      {modal === 'password' && selected && (
        <Modal
          title={'RESET PASSWORD / ' + selected.username}
          subtitle="Share the new password over a trusted channel."
          fields={[passwordField('NEW PASSWORD')]}
          submitLabel="RESET PASSWORD"
          onClose={() => setModal(null)}
          onSubmit={(values) => patch({ password: values.password }, 'OPERATOR PASSWORD RESET')}
        />
      )}
      {modal === 'delete' && selected && (
        <Modal
          title={'DELETE OPERATOR / ' + selected.username + ' ?'}
          subtitle="Removes this panel account. Directory, SSH and audit data are not changed."
          fields={[]}
          danger
          submitLabel="DELETE OPERATOR"
          onClose={() => setModal(null)}
          onSubmit={async () => {
            await api('/api/operators/' + selected.id, { method: 'DELETE' });
            notify('OPERATOR DELETED', 'ok');
            setSelectedId(null);
            await load();
          }}
        />
      )}
    </Panel>
  );
}
