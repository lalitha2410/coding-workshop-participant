/** Display formatters (money, dates, percentages, relative deadlines). */

const money = new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD', notation: 'compact', maximumFractionDigits: 1,
});

export function fmtMoney(n) {
  const v = Number(n);
  return Number.isFinite(v) ? money.format(v) : '—';
}

export function fmtMoneyFull(n) {
  const v = Number(n);
  return Number.isFinite(v)
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(v)
    : '—';
}

export function fmtDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

/**
 * Parse a backend timestamp into an absolute instant.
 *
 * The backend now serializes timestamps as timezone-aware (TIMESTAMPTZ → an ISO
 * string with an offset like `+05:30` or `Z`), so those parse unambiguously. As
 * a defensive fallback, a *naive* string (no offset) is assumed to be UTC — the
 * conventional default — rather than silently reinterpreted as the viewer's
 * local time, which would skew relative times by the local offset.
 */
function parseTs(value) {
  if (!value) return null;
  let s = String(value);
  if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(s)) s = s.replace(' ', 'T') + 'Z';
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}

// Beyond this age, an exact date is more useful than "23 days ago".
const RELATIVE_MAX_DAYS = 7;

/** Absolute date only, e.g. "23 Jul 2026". */
export function fmtAbsDate(value) {
  const d = parseTs(value);
  if (!d) return '—';
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Full, exact timestamp for tooltips, e.g. "23 Jul 2026, 14:32". */
export function fmtDateTime(value) {
  const d = parseTs(value);
  if (!d) return '—';
  return d.toLocaleString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  });
}

/** Relative time like "2 hours ago" / "just now". `now` is injectable for tests. */
export function fmtRelative(value, now = Date.now()) {
  const d = parseTs(value);
  if (!d) return '—';
  const secs = Math.round((now - d.getTime()) / 1000);
  const future = secs < 0;
  const s = Math.abs(secs);
  const phrase = relativePhrase(s);
  if (phrase === 'just now') return phrase;
  return future ? `in ${phrase}` : `${phrase} ago`;
}

/**
 * Relative time for recent events, falling back to an absolute date once an
 * entry is older than RELATIVE_MAX_DAYS (so an audit log reads "5 hours ago" but
 * "23 Jul 2026" rather than an unhelpful "23 days ago").
 */
export function fmtRelativeOrDate(value, now = Date.now()) {
  const d = parseTs(value);
  if (!d) return '—';
  const ageMs = now - d.getTime();
  if (ageMs > RELATIVE_MAX_DAYS * 86400000) return fmtAbsDate(value);
  return fmtRelative(value, now);
}

function relativePhrase(s) {
  const mins = Math.round(s / 60);
  const hours = Math.round(s / 3600);
  const days = Math.round(s / 86400);
  if (s < 45) return 'just now';
  if (s < 90) return 'a minute';
  if (mins < 45) return `${mins} minutes`;
  if (mins < 90) return 'an hour';
  if (hours < 24) return `${hours} hours`;
  if (hours < 36) return 'a day';
  if (days < 30) return `${days} days`;
  if (days < 45) return 'a month';
  if (days < 365) return `${Math.round(days / 30)} months`;
  const years = Math.round(days / 365);
  return years <= 1 ? 'a year' : `${years} years`;
}

export function fmtPct(n, digits = 0) {
  const v = Number(n);
  return Number.isFinite(v) ? `${v.toFixed(digits)}%` : '—';
}

export function daysUntil(value) {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return Math.ceil((d.getTime() - Date.now()) / 86400000);
}

/**
 * A project is "at risk" when it's still in flight but the deadline is imminent/
 * past, or the budget is nearly/over consumed. Derived client-side (not a stored
 * status) — mirrors how a PM would read the data.
 */
export function isAtRisk(project) {
  if (!project) return false;
  if (['completed', 'cancelled'].includes(project.status)) return false;
  const d = daysUntil(project.deadline);
  const deadlineRisk = d !== null && d <= 14;
  const planned = Number(project.budget_planned) || 0;
  const consumed = Number(project.budget_consumed) || 0;
  const budgetRisk = planned > 0 && consumed / planned >= 0.9;
  return deadlineRisk || budgetRisk;
}
