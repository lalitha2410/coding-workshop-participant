import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

const SERVICES = ['auth', 'projects', 'deliverables', 'resources', 'allocations'];

// Parse a JSON env value that may be wrapped in single/double quotes.
function parseJson(raw) {
  if (!raw) return {};
  try {
    return JSON.parse(raw.trim().replace(/^'(.*)'$/s, '$1').replace(/^"(.*)"$/s, '$1'));
  } catch {
    return {};
  }
}

// Normalize keys (short name OR "coding-workshop-<svc>-<id>") -> short service name.
function normalize(map) {
  const out = {};
  for (const [key, url] of Object.entries(map)) {
    if (!url) continue;
    const svc = SERVICES.find((s) => key === s || key.includes(`-${s}-`) || key.endsWith(`-${s}`));
    if (svc) out[svc] = String(url).replace(/\/+$/, '');
  }
  return out;
}

/**
 * Build a same-origin dev proxy so the browser never makes cross-origin calls to
 * the LocalStack Lambda URLs (which browsers block via CORS). Each service gets a
 * /api/<service> prefix forwarded to its Lambda URL from .env.local
 * (VITE_LAMBDA_URLS), with changeOrigin so LocalStack routes by the Lambda-URL
 * subdomain host. The /api prefix is stripped before forwarding, so the Lambda
 * sees the path it expects (e.g. /auth/login, /projects/123).
 *
 * URLs come entirely from env — nothing is hardcoded. Relative endpoints (cloud,
 * e.g. "/api/projects") are skipped: there, the built app is already same-origin.
 */
function buildProxy(env) {
  const services = { ...normalize(parseJson(env.VITE_API_ENDPOINTS)), ...normalize(parseJson(env.VITE_LAMBDA_URLS)) };
  const proxy = {};
  for (const [name, target] of Object.entries(services)) {
    if (!/^https?:\/\//.test(target)) continue; // only proxy absolute (local) URLs
    proxy[`/api/${name}`] = {
      target,
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
      configure: (p) => {
        // The proxy -> Lambda hop is server-to-server. LocalStack Lambda Function
        // URLs return 403 for an actual request that carries a browser Origin
        // header (even with allow_origins '*'), and browsers send Origin on
        // same-origin POST/PUT/DELETE. Strip Origin/Referer so it matches the
        // working direct curl. The browser still sees a same-origin response.
        p.on('proxyReq', (proxyReq) => {
          proxyReq.removeHeader('origin');
          proxyReq.removeHeader('referer');
        });
      },
    };
  }
  return proxy;
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy: buildProxy(env),
    },
    // Vitest — pure-logic unit tests run in a plain Node environment.
    test: {
      environment: 'node',
      include: ['src/**/*.test.{js,jsx}'],
    },
  };
});
