/**
 * Auth service calls (maps to backend/auth: register / login / me).
 */

import { api } from './client';

export function login({ identifier, password }) {
  // Backend accepts either username or email; send whichever the user typed.
  const looksLikeEmail = identifier.includes('@');
  const body = looksLikeEmail ? { email: identifier, password } : { username: identifier, password };
  return api.post('auth', '/auth/login', body, { auth: false });
}

export function register({ username, email, password }) {
  return api.post('auth', '/auth/register', { username, email, password }, { auth: false });
}

export function me() {
  return api.get('auth', '/auth/me');
}
