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
 * Parse a backend timestamp. PostgreSQL NOW() is serialized without a timezone
 * suffix; the DB runs in UTC, so treat a naive ISO string as UTC (append 'Z')
 * to avoid a local-offset skew in relative times.
 */
function parseTs(value) {
  if (!value) return null;
  let s = String(value);
  if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(s)) s = s.replace(' ', 'T') + 'Z';
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Full, exact timestamp for tooltips, e.g. "Jul 23, 2026, 10:04 AM". */
export function fmtDateTime(value) {
  const d = parseTs(value);
  if (!d) return '—';
  return d.toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit',
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
