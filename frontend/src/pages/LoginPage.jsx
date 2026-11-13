import { useEffect, useState } from 'react';
import { Command, KeyRound } from 'lucide-react';
import { api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { useSession } from '../session.jsx';
import { versionLabel } from '../version.js';

export function Login() {
  const { refresh } = useSession();
  const [user, setUser] = useState('admin'),
    [pass, setPass] = useState(''),
    [err, setErr] = useState(''),
    [busy, setBusy] = useState(false),
    [apiVersion, setApiVersion] = useState('');
  useEffect(() => {
    // Unauthenticated health check: only used to show a version mismatch.
    api('/api/health')
      .then((health) => setApiVersion(health?.version || ''))
      .catch(() => {});
  }, []);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      // The backend answers with an httpOnly session cookie; nothing is stored by script.
      await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: user, password: pass }),
      });
      setPass('');
      if (!(await refresh())) setErr('Signed in, but the session could not be read. Try again.');
    } catch (x) {
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-screen">
      <div className="boot-lines">
        RSAT FULL SYSTEM CONSOLE
        <br />
        CROSS-PLATFORM DIRECTORY ADMINISTRATION
        <br />
        BUILD {versionLabel(apiVersion)} / SECURE SESSION
      </div>
      <form className="login" onSubmit={submit}>
        <div className="terminal-mark">
          <Command size={22} />
        </div>
        <div className="eyebrow">AUTHORIZED OPERATORS ONLY</div>
        <h1>RSAT//FULL</h1>
        <p>ADMINISTRATION TERMINAL FOR macOS + LINUX</p>
        <label>
          <span>OPERATOR</span>
          <input
            autoFocus
            autoComplete="username"
            value={user}
            onChange={(e) => setUser(e.target.value)}
          />
        </label>
        <label>
          <span>PASSWORD</span>
          <input
            type="password"
            autoComplete="current-password"
            value={pass}
            onChange={(e) => setPass(e.target.value)}
          />
        </label>
        {err && (
          <div className="error-box" role="alert">
            {err}
          </div>
        )}
        <Button type="submit" kind="primary" icon={KeyRound} disabled={busy}>
          {busy ? 'AUTHENTICATING' : 'ENTER SYSTEM'}
        </Button>
        <small>ACCESS IS LOGGED AND AUDITED</small>
      </form>
    </div>
  );
}
