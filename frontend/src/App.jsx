import { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { LogOut, RefreshCw, Terminal } from 'lucide-react';
import { api } from './api.js';
import { nav } from './navigation.js';
import { canOpenSection, hasPermission, resolveSection } from './permissions.mjs';
import { useSession } from './session.jsx';
import { emptySessions, sessionReducer } from './ssh-sessions.mjs';
import { versionLabel } from './version.js';
import { AccountDialog } from './components/AccountDialog.jsx';
import { BottomDock } from './components/BottomDock.jsx';
import { Button } from './components/Button.jsx';
import { DirectoryTree } from './components/DirectoryTree.jsx';
import { NativeUnavailable } from './components/NativeUnavailable.jsx';
import { Panel } from './components/Panel.jsx';
import { ServiceConnection } from './components/ServiceConnection.jsx';
import { SshSessionWorkspace } from './components/SshSessionWorkspace.jsx';
import { Toast } from './components/Toast.jsx';
import { AuditPage } from './pages/AuditPage.jsx';
import { ComputersPage } from './pages/ComputersPage.jsx';
import { DHCPPage } from './pages/DHCPPage.jsx';
import { DNSPage } from './pages/DNSPage.jsx';
import { Domain } from './pages/DomainPage.jsx';
import { FilesPage } from './pages/FilesPage.jsx';
import { GPOPage, NativeGPO } from './pages/GPOPage.jsx';
import { GroupsPage } from './pages/GroupsPage.jsx';
import { Login } from './pages/LoginPage.jsx';
import { OUsPage } from './pages/OUsPage.jsx';
import { Overview } from './pages/OverviewPage.jsx';
import { RecyclePage } from './pages/RecyclePage.jsx';
import { LinuxServersPage, SSHPage } from './pages/SSHInventoryPage.jsx';
import { SettingsPage } from './pages/SettingsPage.jsx';
import { UsersPage } from './pages/UsersPage.jsx';

// Shell status (domain summary, DC list, recent audit) refresh interval. Each
// refresh is a directory round trip in direct mode, so it pauses while hidden.
const SHELL_POLL_MS = 60000;

const PAGES = {
  overview: Overview,
  domain: Domain,
  users: UsersPage,
  groups: GroupsPage,
  computers: ComputersPage,
  ous: OUsPage,
  recycle: RecyclePage,
  dns: DNSPage,
  dhcp: DHCPPage,
  gpo: GPOPage,
  audit: AuditPage,
  ssh: SSHPage,
  linux: LinuxServersPage,
  files: FilesPage,
  settings: SettingsPage,
};
const SECTION_ORDER = nav.map(([id]) => id);

/** Chooses between the session check, the login screen and the signed-in console. */
export function Root() {
  const session = useSession();
  if (session.status === 'loading')
    return (
      <div className="login-screen">
        <div className="boot-lines">
          RSAT FULL SYSTEM CONSOLE
          <br />
          CHECKING SESSION...
        </div>
      </div>
    );
  if (session.status === 'error')
    return (
      <div className="login-screen">
        <div className="login">
          <div className="eyebrow">CONTROL PLANE UNREACHABLE</div>
          <div className="error-box" role="alert">
            {session.error}
          </div>
          <Button kind="primary" icon={RefreshCw} onClick={session.refresh}>
            RETRY
          </Button>
        </div>
      </div>
    );
  if (session.status !== 'signed-in') return <Login />;
  return <App key={session.me.username} />;
}

export function App() {
  const { me, signOut } = useSession();
  const permissions = me?.permissions;
  const permissionsRef = useRef(permissions);
  permissionsRef.current = permissions;
  const lastShellRefresh = useRef(0);

  const [sshSessions, sessionDispatch] = useReducer(sessionReducer, emptySessions);
  function openSsh(device, baseUrl) {
    sessionDispatch({ type: 'open', id: crypto.randomUUID(), device, baseUrl });
  }
  const liveSsh = sshSessions.items.some((x) => ['CONNECTING', 'CONNECTED'].includes(x.status));
  useEffect(() => {
    if (!liveSsh) return;
    const warn = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [liveSsh]);
  const [section, setSection] = useState(
      () =>
        resolveSection(permissions, location.hash.slice(1) || 'users', [
          ...SECTION_ORDER,
          'recycle',
        ]) || 'users',
    ),
    [revision, setRevision] = useState(0),
    [toast, setToast] = useState(null),
    [accountOpen, setAccountOpen] = useState(false),
    [clock, setClock] = useState(new Date()),
    [shell, setShell] = useState({
      summary: null,
      controllers: [],
      replication: [],
      ous: [],
      audit: [],
      health: null,
    });
  function notify(text, kind = 'ok') {
    setToast({ text, kind });
    setTimeout(() => setToast(null), 3200);
  }
  async function refreshShell() {
    lastShellRefresh.current = Date.now();
    const allowed = (permission) => hasPermission(permissionsRef.current, permission);
    // Only ask for what this role may read; a refused call would just be noise.
    const optional = (permitted, path, fallback) =>
      permitted ? api(path).catch(() => fallback) : Promise.resolve(fallback);
    const health = await api('/api/health').catch(() => null);
    // Direct mode has no replication endpoint (always 501), so it is not requested.
    const native = health?.connection_mode === 'native';
    const [summary, controllers, replication, ous, audit, settings] = await Promise.all([
      optional(allowed('domain.read'), '/api/domain/summary', null),
      optional(allowed('domain.read'), '/api/domain/controllers', []),
      optional(allowed('domain.read') && !native, '/api/domain/replication', []),
      optional(allowed('ou.read'), '/api/ad/ous', []),
      optional(allowed('audit.read'), '/api/audit?limit=12', []),
      optional(allowed('settings.read'), '/api/settings', null),
    ]);
    setShell({
      summary,
      controllers: controllers || [],
      replication: replication || [],
      ous: ous || [],
      audit: audit || [],
      health,
      settings,
    });
  }
  useEffect(() => {
    refreshShell();
    const tick = setInterval(() => setClock(new Date()), 1000);
    const poll = setInterval(() => {
      if (!document.hidden) refreshShell();
    }, SHELL_POLL_MS);
    const becameVisible = () => {
      if (!document.hidden && Date.now() - lastShellRefresh.current >= SHELL_POLL_MS)
        refreshShell();
    };
    const settingsChanged = () => {
      refreshShell();
      setRevision((x) => x + 1);
    };
    document.addEventListener('visibilitychange', becameVisible);
    window.addEventListener('directory-settings-changed', settingsChanged);
    return () => {
      clearInterval(tick);
      clearInterval(poll);
      document.removeEventListener('visibilitychange', becameVisible);
      window.removeEventListener('directory-settings-changed', settingsChanged);
    };
  }, []);
  function leave() {
    if (liveSsh && !window.confirm('Signing out closes all open SSH sessions. Continue?')) return;
    signOut();
  }
  const Page = useMemo(() => PAGES[section] || Overview, [section]);
  const native = shell.health?.connection_mode === 'native';
  const permitted = canOpenSection(permissions, section);
  const domain = (
      shell.summary?.domain ||
      shell.settings?.native?.domain ||
      'DIRECTORY.LOCAL'
    ).toUpperCase(),
    dc = shell.controllers?.[0]?.name || '—';
  return (
    <div className="admin-desktop">
      <header className="app-titlebar">
        <div className="app-ident">
          <span className="app-icon">▣</span>
          <b>RSAT FULL :: ACTIVE DIRECTORY ADMINISTRATION CENTER</b>
          <small>v{versionLabel(shell.health?.version)}</small>
        </div>
        <div className="connection-strip">
          <span className={shell.summary ? 'connected' : 'red-text'}>
            [ {shell.summary ? 'Connected' : 'Directory offline'} ]
          </span>
          <span>
            Domain: <b className="green-text">{domain}</b>
          </span>
          <span>
            DC: <u>{dc}</u>
          </span>
          <span>
            {clock.toLocaleDateString()} &nbsp; {clock.toLocaleTimeString()}
          </span>
          <span className="titlebar-account">
            <button type="button" title="My account" onClick={() => setAccountOpen(true)}>
              ▣ &nbsp; {me.username} · {String(me.role || '').toUpperCase()}
            </button>
            <button type="button" title="Sign out of this browser" onClick={leave}>
              <LogOut size={11} /> SIGN OUT
            </button>
          </span>
        </div>
      </header>
      <nav className="module-tabs" aria-label="Management modules">
        {nav
          .filter(([id]) => canOpenSection(permissions, id))
          .map(([id, num, label, Icon]) => (
            <button
              key={id}
              title={label}
              aria-current={section === id ? 'page' : undefined}
              className={section === id ? 'active' : ''}
              onClick={() => setSection(id)}
            >
              <span>[{num}]</span>
              <Icon size={13} />
              <span>{label}</span>
            </button>
          ))}
        {sshSessions.items.length > 0 && (
          <button
            className={section === 'ssh-sessions' ? 'active' : ''}
            onClick={() => setSection('ssh-sessions')}
          >
            <Terminal size={13} /> SSH SESSIONS ({sshSessions.items.length})
          </button>
        )}
      </nav>
      <div className="desktop-main">
        <DirectoryTree section={section} setSection={setSection} shell={shell} />
        <div className="page-host">
          {section === 'ssh-sessions' ? null : !permitted ? (
            <Panel title={section.toUpperCase()} code="403">
              <div className="identity-model-note">
                <div>
                  <b>NOT AVAILABLE FOR YOUR ROLE</b>
                  <span>
                    The {String(me.role || 'current')} role does not include this module. Ask an
                    administrator if you need access.
                  </span>
                </div>
              </div>
            </Panel>
          ) : !shell.health ? (
            <div className="loading">READING CONNECTION SETTINGS...</div>
          ) : native && ['recycle'].includes(section) ? (
            <NativeUnavailable section={section} />
          ) : native && section === 'gpo' ? (
            <NativeGPO key={revision} notify={notify} />
          ) : native && ['dns', 'dhcp'].includes(section) ? (
            <ServiceConnection key={section + revision} notify={notify}>
              <Page notify={notify} native />
            </ServiceConnection>
          ) : (
            <Page
              key={section === 'settings' ? 'settings' : revision}
              navigate={setSection}
              onOpenSsh={openSsh}
              sshSessions={sshSessions.items}
              notify={notify}
              native={native}
            />
          )}
          <SshSessionWorkspace
            state={sshSessions}
            dispatch={sessionDispatch}
            visible={['ssh', 'linux', 'ssh-sessions'].includes(section)}
          />
        </div>
      </div>
      <BottomDock shell={shell} section={section} />
      <Toast toast={toast} />
      {accountOpen && <AccountDialog notify={notify} onClose={() => setAccountOpen(false)} />}
    </div>
  );
}
