import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, getSession, onSessionExpired, setSession } from '../lib/api';

const AuthContext = createContext(null);

/** Rank order mirrors the server's ROLE_RANK. The UI hides; the server enforces. */
const RANK = { INSPECTOR: 1, SENIOR_OFFICER: 2, ADMIN: 3 };

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => getSession()?.user ?? null);
  const [loading, setLoading] = useState(Boolean(getSession()));

  const signOut = useCallback(() => {
    setSession(null);
    setUser(null);
  }, []);

  useEffect(() => {
    onSessionExpired(() => setUser(null));
  }, []);

  // Revalidate a stored session on load: the account may have been deactivated
  // or its role changed since the token was issued.
  useEffect(() => {
    if (!getSession()) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    api.auth
      .me()
      .then((fresh) => {
        if (!cancelled) setUser(fresh);
      })
      .catch(() => {
        if (!cancelled) signOut();
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [signOut]);

  const signIn = useCallback(async (email, password) => {
    const session = await api.auth.login(email, password);
    setSession(session);
    setUser(session.user);
    return session.user;
  }, []);

  const register = useCallback(async (payload) => {
    const session = await api.auth.register(payload);
    setSession(session);
    setUser(session.user);
    return session.user;
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      signIn,
      register,
      signOut,
      isAuthenticated: Boolean(user),
      hasRole: (minimum) => (RANK[user?.role] ?? 0) >= (RANK[minimum] ?? 99),
    }),
    [user, loading, signIn, register, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}
