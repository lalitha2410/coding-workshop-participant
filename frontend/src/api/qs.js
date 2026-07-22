/** Build a query string from an object, skipping null/undefined/empty values. */
export function qs(params = {}) {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    p.append(k, v);
  }
  const s = p.toString();
  return s ? `?${s}` : '';
}
