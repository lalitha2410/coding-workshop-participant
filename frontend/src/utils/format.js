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
