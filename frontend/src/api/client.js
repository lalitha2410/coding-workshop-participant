/**
 * Thin fetch wrapper for the Meridian backend services.
 *
 * Calls are made SAME-ORIGIN through the /api/<service> prefix. In dev, the Vite
 * proxy (see vite.config.js) forwards those to the LocalStack Lambda URLs from
 * .env.local; in the cloud build the gateway serves /api/* directly. Either way
 * the browser never makes a cross-origin request, so CORS can't block it.
 *
 * By convention `path` already starts with the service segment (e.g. "/auth/login",
 * "/projects/123"), so `/api` + path routes to the correct service proxy.
 *
 * - Attaches the JWT bearer token to every request (forwarded through the proxy).
 * - Normalizes responses to parsed JSON, and errors to ApiError{status,message}.
 * - Surfaces 401 (unauthenticated) globally so the app can bounce to /login;
 *   403 (forbidden) is thrown for the caller/route to route to /not-permitted.
 */

import { getToken } from './token';

export class ApiError extends Error {
  constructor(status, message, details) {
    super(message || `Request failed (${status})`);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
  }
}

// Registered by the auth context; invoked on any 401 so a stale/expired token
// logs the user out and returns them to the sign-in screen.
let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function request(service, path, { method = 'GET', body, auth = true, signal } = {}) {
  // Same-origin path: /api/<service>/... routed by the dev proxy / cloud gateway.
  const url = `/api${path}`;

  const headers = { 'Content-Type': 'application/json' };
  const token = getToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body != null ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (err) {
    throw new ApiError(0, 'Network error — is the backend reachable?', String(err));
  }

  // 204 No Content (deletes) — nothing to parse.
  if (res.status === 204) return null;

  let data = null;
  const text = await res.text();
  if (text) {
    try { data = JSON.parse(text); } catch { data = { raw: text }; }
  }

  if (res.ok) return data;

  const message = (data && (data.error || data.message)) || `Request failed (${res.status})`;
  if (res.status === 401 && auth && typeof onUnauthorized === 'function') {
    onUnauthorized();
  }
  throw new ApiError(res.status, message, data && data.details);
}

export const api = {
  get: (service, path, opts) => request(service, path, { ...opts, method: 'GET' }),
  post: (service, path, body, opts) => request(service, path, { ...opts, method: 'POST', body }),
  put: (service, path, body, opts) => request(service, path, { ...opts, method: 'PUT', body }),
  del: (service, path, opts) => request(service, path, { ...opts, method: 'DELETE' }),
};
