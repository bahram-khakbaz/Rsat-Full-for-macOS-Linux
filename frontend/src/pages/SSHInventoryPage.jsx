import { useEffect, useState } from 'react';
import { Folder, KeyRound, Plus, RefreshCw, ShieldCheck, Terminal, Trash2 } from 'lucide-react';
import { api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Status } from '../components/Status.jsx';
import { Modal } from '../components/Modal.jsx';
import { Table } from '../components/Table.jsx';
import { Panel } from '../components/Panel.jsx';
import IpamPanel from '../components/IpamPanel.jsx';

export function SSHPage(props) {
  return <SSHInventoryPage {...props} kind="switches" />;
}

export function LinuxServersPage(props) {
  return <SSHInventoryPage {...props} kind="linux-servers" />;
}

export function SSHInventoryPage({ notify, kind, navigate, onOpenSsh, sshSessions = [] }) {
  const linux = kind === 'linux-servers',
    baseUrl = '/api/ssh/' + kind,
    deviceLabel = linux ? 'SERVER' : 'SWITCH';

  const [rows, setRows] = useState([]),
    [sel, setSel] = useState(null),
    [modal, setModal] = useState(null),
    [key, setKey] = useState(null),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  async function load() {
    try {
      setRows(await api(baseUrl));
      setError('');
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    load();
  }, []);
  async function inspect() {
    setBusy(true);
    setError('');
    try {
      setKey(await api(baseUrl + '/' + sel.id + '/inspect', { method: 'POST' }));
      setModal('trust');
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const fields = [
    { name: 'name', label: deviceLabel + ' NAME' },
    { name: 'host', label: 'IP ADDRESS / HOSTNAME' },
    { name: 'port', label: 'SSH PORT', type: 'number', default: 22 },
    { name: 'username', label: 'YOUR ' + deviceLabel + ' USERNAME' },
    {
      name: 'password',
      label: modal === 'edit' ? 'PASSWORD (EMPTY KEEPS SAVED PASSWORD)' : deviceLabel + ' PASSWORD',
      type: 'password',
    },
    { name: 'vault_key', label: 'VAULT AGENT KEY (OPTIONAL; LEAVE PASSWORD BLANK)' },
  ];
  async function save(v) {
    const r = await api(baseUrl + (modal === 'edit' ? '/' + sel.id : ''), {
      method: modal === 'edit' ? 'PUT' : 'POST',
      body: JSON.stringify({ ...v, port: Number(v.port) }),
    });
    setSel(r);
    notify(deviceLabel + ' SAVED', 'ok');
    await load();
  }
  return (
    <div className="stack ssh-page">
      {error && <div className="error-box">{error}</div>}
      <Panel
        title={(linux ? 'LINUX SERVERS / ' : 'SAVED SSH SWITCHES / ') + rows.length}
        code="SSH"
        actions={
          <>
            <Button perm="ssh.write" icon={Plus} kind="primary" onClick={() => setModal('new')}>
              ADD {deviceLabel}
            </Button>
            <Button icon={RefreshCw} onClick={load}>
              REFRESH
            </Button>
          </>
        }
      >
        <div className="identity-model-note">
          <div>
            <b>DIRECT SSH FROM THE MAC</b>
            <span>
              {linux
                ? 'Save your Linux servers here and open an interactive SSH terminal.'
                : 'Switch accounts are separate from Active Directory.'}{' '}
              Passwords are encrypted in local storage and used only after the host key is approved.
            </span>
          </div>
        </div>
        <Table
          rows={rows}
          selectedKey={sel?.id}
          onRow={(r) => {
            setSel(r);
            setKey(null);
            setError('');
          }}
          cols={[
            { key: 'name', label: 'NAME' },
            { key: 'host', label: 'HOST' },
            { key: 'port', label: 'PORT' },
            { key: 'username', label: 'ACCOUNT', render: (v) => v || 'NEEDED' },
            {
              key: 'password_configured',
              label: 'CREDENTIAL',
              render: (v, r) =>
                !v
                  ? 'NEEDED'
                  : r.credential_source === 'vault-agent'
                    ? 'VAULT AGENT'
                    : 'LOCAL / ENCRYPTED',
            },
            {
              key: 'login',
              label: 'LOGIN',
              render: (_, r) => (
                <Status ok={Boolean(r.username && r.password_configured && r.fingerprint)}>
                  {!r.username
                    ? 'ACCOUNT NEEDED'
                    : !r.password_configured
                      ? 'PASSWORD NEEDED'
                      : !r.fingerprint
                        ? 'VERIFY KEY'
                        : 'READY'}
                </Status>
              ),
            },
            {
              key: 'fingerprint',
              label: 'HOST KEY',
              render: (v) => <Status ok={Boolean(v)}>{v ? 'APPROVED' : 'VERIFY FIRST'}</Status>,
            },
          ]}
        />
        {sel && (
          <div className="inline-tools">
            <span className="ssh-login-status">
              {!sel.fingerprint
                ? 'Verify the host key first.'
                : !sel.username
                  ? 'Host key approved · SSH username is missing.'
                  : !sel.password_configured
                    ? 'Host key approved · SSH password is missing.'
                    : 'Host key and login configured · Ready to connect.'}
            </span>
            <Button perm="ssh.write" icon={KeyRound} onClick={() => setModal('edit')}>
              EDIT / CREDENTIALS
            </Button>
            <Button perm="ssh.write" icon={ShieldCheck} disabled={busy} onClick={inspect}>
              {busy ? 'INSPECTING...' : 'VERIFY HOST KEY'}
            </Button>
            <Button
              perm="ssh.connect"
              icon={Terminal}
              kind="primary"
              disabled={!sel.fingerprint}
              onClick={() => {
                if (!sel.password_configured || !sel.username) {
                  setError(
                    'The host key is approved. Save this SSH username and password to connect.',
                  );
                  setModal('edit');
                } else {
                  setError('');
                  onOpenSsh(sel, baseUrl);
                }
              }}
            >
              CONNECT
            </Button>
            <Button
              perm="sftp.read"
              icon={Folder}
              onClick={() => {
                sessionStorage.setItem(
                  'rsat_file_target',
                  (linux ? 'linux' : 'switch') + ':' + sel.id,
                );
                navigate('files');
              }}
            >
              FILES / SFTP
            </Button>
            <Button
              perm="ssh.write"
              icon={Trash2}
              kind="danger"
              disabled={sshSessions.some(
                (x) =>
                  x.baseUrl === baseUrl &&
                  x.device.id === sel.id &&
                  ['CONNECTING', 'CONNECTED'].includes(x.status),
              )}
              onClick={() => setModal('delete')}
            >
              DELETE
            </Button>
          </div>
        )}
      </Panel>
      {linux && <IpamPanel api={api} ui={{ Panel, Button, Modal, Table }} />}
      {(modal === 'new' || modal === 'edit') && (
        <Modal
          title={(modal === 'edit' ? 'EDIT SSH ' : 'ADD SSH ') + deviceLabel}
          subtitle="Use a local password OR a Vault Agent key. Clear the key to switch to a password. Leave both blank to keep the saved credential."
          fields={fields}
          initial={modal === 'edit' ? { ...sel, password: '' } : {}}
          submitLabel={'SAVE ' + deviceLabel}
          onClose={() => setModal(null)}
          onSubmit={save}
        />
      )}
      {modal === 'trust' && key && (
        <Modal
          title={'VERIFY ' + deviceLabel + ' HOST KEY'}
          subtitle={
            'Compare this SHA256 fingerprint with the host console or a trusted administrator before approving. ' +
            key.host +
            ':' +
            key.port
          }
          fields={[]}
          submitLabel="APPROVE HOST KEY"
          onClose={() => setModal(null)}
          onSubmit={async () => {
            const r = await api(baseUrl + '/' + sel.id + '/trust', {
              method: 'POST',
              body: JSON.stringify({ fingerprint: key.fingerprint }),
            });
            setSel(r);
            load();
          }}
        >
          <div className="ssh-fingerprint">
            <b>{key.algorithm}</b>
            <code>{key.fingerprint}</code>
            <span>
              Approval is required only once. A changed host key blocks login before sending your
              password.
            </span>
          </div>
        </Modal>
      )}
      {modal === 'delete' && sel && (
        <Modal
          title={'REMOVE ' + deviceLabel + ' / ' + sel.name}
          fields={[]}
          danger
          submitLabel="REMOVE"
          onClose={() => setModal(null)}
          onSubmit={async () => {
            await api(baseUrl + '/' + sel.id, { method: 'DELETE' });
            setSel(null);
            await load();
          }}
        />
      )}
    </div>
  );
}
