/**
 * Auth context: holds the current user + role, and the login/register/logout
 * actions. Bootstraps from a persisted token by calling /auth/me, and wires the
 * API client's global 401 handler to log out.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { login as apiLogin, register as apiRegister, me as apiMe } from '../api/auth';
import { setToken, clearToken, getToken } from '../api/token';
import { setUnauthorizedHandler } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | authed | anon

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    setStatus('anon');
  }, []);

  // Bounce to sign-in whenever any request comes back 401.
  useEffect(() => {
    setUnauthorizedHandler(() => logout());
  }, [logout]);

  // Rehydrate session on first load if a token is present.
  useEffect(() => {
    let active = true;
    (async () => {
      if (!getToken()) { setStatus('anon'); return; }
      try {
        const current = await apiMe();
        if (active) { setUser(current); setStatus('authed'); }
      } catch {
        if (active) { clearToken(); setUser(null); setStatus('anon'); }
      }
    })();
    return () => { active = false; };
  }, []);

  const login = useCallback(async (identifier, password) => {
    const res = await apiLogin({ identifier, password });
    setToken(res.token);
    setUser(res.user);
    setStatus('authed');
    return res.user;
  }, []);

  const register = useCallback(async ({ username, email, password }) => {
    await apiRegister({ username, email, password });
    // Seamless first impression: sign them straight in after registering.
    return login(username, password);
  }, [login]);

  const value = useMemo(() => ({
    user,
    role: user?.role ?? null,
    status,
    isAuthenticated: status === 'authed',
    isBootstrapping: status === 'loading',
    login,
    register,
    logout,
  }), [user, status, login, register, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}
