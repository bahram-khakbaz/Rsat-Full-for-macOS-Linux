import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, UNAUTHORIZED_EVENT } from './api.js';
import { hasPermission } from './permissions.mjs';

const LEGACY_TOKEN_KEY = 'rsat_token';
const SessionContext = createContext(null);

/**
 * Tracks the signed-in operator. The session itself is an httpOnly cookie, so
 * the only way to know its state is to ask the API (`GET /api/auth/me`).
 */
export function SessionProvider({ children }) {
  const [state, setState] = useState({ status: 'loading', me: null, error: '' });

  const refresh = useCallback(async () => {
    try {
      const me = await api('/api/auth/me');
      setState({ status: 'signed-in', me, error: '' });
      return me;
    } catch (error) {
      setState(
        error.status === 401
          ? { status: 'signed-out', me: null, error: '' }
          : { status: 'error', me: null, error: error.message },
      );
      return null;
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api('/api/auth/logout', { method: 'POST' });
    } catch {
      // The cookie may already be invalid; the UI still returns to the login screen.
    }
    setState({ status: 'signed-out', me: null, error: '' });
  }, []);

  useEffect(() => {
    try {
      // Earlier builds kept a bearer token in localStorage; remove any leftover copy.
      localStorage.removeItem(LEGACY_TOKEN_KEY);
    } catch {
      // Storage can be unavailable in hardened browsers; nothing to clean up then.
    }
    refresh();
    const expired = () => setState({ status: 'signed-out', me: null, error: '' });
    window.addEventListener(UNAUTHORIZED_EVENT, expired);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, expired);
  }, [refresh]);

  const value = useMemo(
    () => ({
      ...state,
      refresh,
      signOut,
      can: (permission) => hasPermission(state.me?.permissions, permission),
    }),
    [state, refresh, signOut],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const session = useContext(SessionContext);
  if (!session) throw new Error('useSession must be used inside <SessionProvider>');
  return session;
}
