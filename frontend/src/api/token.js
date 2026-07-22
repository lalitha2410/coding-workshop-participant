/**
 * JWT storage shared by the API client and the auth context.
 *
 * Kept in a tiny standalone module (not React state) so the fetch client can
 * read the current token synchronously on every request without prop drilling.
 * Mirrored to localStorage so a refresh keeps the session.
 */

const STORAGE_KEY = 'meridian_token';

let current = (() => {
  try { return localStorage.getItem(STORAGE_KEY) || null; } catch { return null; }
})();

export function getToken() {
  return current;
}

export function setToken(token) {
  current = token || null;
  try {
    if (token) localStorage.setItem(STORAGE_KEY, token);
    else localStorage.removeItem(STORAGE_KEY);
  } catch { /* ignore */ }
}

export function clearToken() {
  setToken(null);
}
