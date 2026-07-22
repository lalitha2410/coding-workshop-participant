/**
 * Resolves per-service backend base URLs from the generated env config —
 * never hardcoded. `bin/generate-env.sh` writes VITE_API_ENDPOINTS (and
 * VITE_LAMBDA_URLS) into frontend/.env.local as a JSON map of
 * { serviceName: baseUrl }, keyed by short service name (auth, projects, ...).
 *
 * The app_id suffix in Lambda URLs changes per environment, which is exactly
 * why these must come from config at build/deploy time, not source.
 */

const SERVICES = ['auth', 'projects', 'deliverables', 'resources', 'allocations'];

function parseJsonEnv(raw) {
  if (!raw) return {};
  try {
    // Values may arrive wrapped in single quotes from the .env file.
    const cleaned = raw.trim().replace(/^'(.*)'$/s, '$1');
    return JSON.parse(cleaned);
  } catch {
    return {};
  }
}

// Prefer api_endpoints (short keys); fall back to lambda_urls.
function loadMap() {
  const fromEndpoints = parseJsonEnv(import.meta.env.VITE_API_ENDPOINTS);
  const fromLambdas = parseJsonEnv(import.meta.env.VITE_LAMBDA_URLS);
  const merged = { ...fromLambdas, ...fromEndpoints };

  // Normalize keys like "coding-workshop-auth-abcd1234" -> "auth".
  const normalized = {};
  for (const [key, url] of Object.entries(merged)) {
    if (!url) continue;
    const match = SERVICES.find((s) => key === s || key.includes(`-${s}-`) || key.endsWith(`-${s}`));
    normalized[match || key] = String(url).replace(/\/+$/, '');
  }
  return normalized;
}

const endpointMap = loadMap();

/** Base URL for a service, or '' if not configured (calls will surface an error). */
export function getServiceUrl(service) {
  return endpointMap[service] || '';
}

/** True when at least one service URL is configured. Used to warn in the UI. */
export function hasBackendConfig() {
  return SERVICES.some((s) => !!endpointMap[s]);
}

export { SERVICES };
