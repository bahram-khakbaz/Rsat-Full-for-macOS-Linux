import { useState } from 'react';
import { KeyRound, LogOut } from 'lucide-react';
import { api } from '../api.js';
import { MIN_PANEL_PASSWORD } from '../constants.js';
import { useSession } from '../session.jsx';
import { Button } from './Button.jsx';
import { KV } from './KV.jsx';

/** "My account": change the panel password or end every session of this operator. */
export function AccountDialog({ notify, onClose }) {
  const { me, signOut } = useSession();
  const environmentManaged = me?.managed === 'environment';
  const [form, setForm] = useState({ current: '', next: '', confirm: '' }),
    [busy, setBusy] = useState(''),
    [error, setError] = useState('');
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  async function changePassword(e) {
    e.preventDefault();
    if (form.next !== form.confirm) {
      setError('The new password and its confirmation do not match');
      return;
    }
    setBusy('password');
    setError('');
    try {
      await api('/api/auth/password', {
        method: 'POST',
        body: JSON.stringify({ current_password: form.current, new_password: form.next }),
      });
      notify('PANEL PASSWORD CHANGED', 'ok');
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy('');
    }
  }
  async function signOutEverywhere() {
    setBusy('revoke');
    setError('');
    try {
      await api('/api/auth/revoke-sessions', { method: 'POST' });
      // This browser's session was revoked too; return to the login screen.
      await signOut();
    } catch (err) {
      setError(err.message);
      setBusy('');
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <form className="modal" onSubmit={changePassword}>
        <div className="modal-head">
          <div>
            <span className="eyebrow">MY ACCOUNT</span>
            <h3>{me?.username}</h3>
            <p>Panel sign-in only. This does not change any Active Directory or SSH password.</p>
          </div>
          <button type="button" className="x" onClick={onClose}>
            ×
          </button>
        </div>
        <KV
          items={[
            ['ROLE', me?.role],
            ['ACCOUNT TYPE', environmentManaged ? 'Server environment' : 'Local operator'],
          ]}
        />
        {environmentManaged ? (
          <div className="identity-model-note">
            <span>
              This administrator is defined by the server environment (ADMIN_USERNAME /
              ADMIN_PASSWORD). Change its password in the deployment configuration and restart the
              backend.
            </span>
          </div>
        ) : (
          <div className="form-grid">
            <label>
              <span>CURRENT PASSWORD</span>
              <input
                type="password"
                autoComplete="current-password"
                required
                value={form.current}
                onChange={set('current')}
              />
            </label>
            <label>
              <span>NEW PASSWORD ({MIN_PANEL_PASSWORD}+ CHARACTERS)</span>
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={MIN_PANEL_PASSWORD}
                value={form.next}
                onChange={set('next')}
              />
            </label>
            <label>
              <span>CONFIRM NEW PASSWORD</span>
              <input
                type="password"
                autoComplete="new-password"
                required
                minLength={MIN_PANEL_PASSWORD}
                value={form.confirm}
                onChange={set('confirm')}
              />
            </label>
          </div>
        )}
        {error && (
          <div className="error-box" role="alert">
            {error}
          </div>
        )}
        <div className="modal-actions">
          <Button
            icon={LogOut}
            kind="danger"
            disabled={Boolean(busy)}
            title="Ends every session of this operator, including this one"
            onClick={signOutEverywhere}
          >
            {busy === 'revoke' ? 'SIGNING OUT...' : 'SIGN OUT EVERYWHERE'}
          </Button>
          <Button onClick={onClose}>CLOSE</Button>
          {!environmentManaged && (
            <Button type="submit" kind="primary" icon={KeyRound} disabled={Boolean(busy)}>
              {busy === 'password' ? 'SAVING...' : 'CHANGE PASSWORD'}
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
