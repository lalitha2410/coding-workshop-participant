import { describe, it, expect } from 'vitest';
import { fmtMoney, fmtDate, fmtPct, daysUntil, isAtRisk, fmtRelative, fmtRelativeOrDate, fmtDateTime, fmtAbsDate } from './format';

// Deadline N days from now, as a YYYY-MM-DD string (matches API date shape).
const isoInDays = (n) => new Date(Date.now() + n * 86400000).toISOString().slice(0, 10);

describe('fmtMoney', () => {
  it('formats compactly with a currency symbol', () => {
    expect(fmtMoney(0)).toMatch(/^\$0(\.0)?$/); // "$0" or "$0.0" depending on ICU
    expect(fmtMoney(800000)).toContain('$');
    expect(fmtMoney(800000)).toContain('800');
    expect(fmtMoney(800000)).toContain('K');
    expect(fmtMoney(1200000)).toContain('1.2');
    expect(fmtMoney(1200000)).toContain('M');
  });
  it('returns an em dash for non-numeric input', () => {
    expect(fmtMoney(undefined)).toBe('—');
    expect(fmtMoney('abc')).toBe('—');
  });
});

describe('fmtDate', () => {
  it('formats an ISO date as "Mon D, YYYY"', () => {
    expect(fmtDate('2026-03-25')).toMatch(/^[A-Z][a-z]{2} \d{1,2}, 2026$/);
  });
  it('returns an em dash for missing/invalid dates', () => {
    expect(fmtDate(null)).toBe('—');
    expect(fmtDate('not-a-date')).toBe('—');
  });
});

describe('fmtPct', () => {
  it('appends a percent sign, honoring digits', () => {
    expect(fmtPct(61)).toBe('61%');
    expect(fmtPct(12.5, 1)).toBe('12.5%');
    expect(fmtPct(NaN)).toBe('—');
  });
});

describe('daysUntil', () => {
  it('is null for empty, negative for past, positive for future', () => {
    expect(daysUntil(null)).toBeNull();
    expect(daysUntil('2020-01-01')).toBeLessThan(0);
    expect(daysUntil('2100-01-01')).toBeGreaterThan(0);
  });
});

describe('isAtRisk', () => {
  it('flags an active project with an imminent deadline', () => {
    expect(isAtRisk({ status: 'active', deadline: isoInDays(5), budget_planned: 1000, budget_consumed: 100 })).toBe(true);
  });
  it('flags a project whose budget is nearly/over consumed', () => {
    expect(isAtRisk({ status: 'active', deadline: isoInDays(120), budget_planned: 1000, budget_consumed: 950 })).toBe(true);
  });
  it('does not flag a healthy in-flight project', () => {
    expect(isAtRisk({ status: 'active', deadline: isoInDays(120), budget_planned: 1000, budget_consumed: 100 })).toBe(false);
  });
  it('never flags completed or cancelled projects', () => {
    expect(isAtRisk({ status: 'completed', deadline: isoInDays(-5), budget_planned: 1000, budget_consumed: 1000 })).toBe(false);
    expect(isAtRisk({ status: 'cancelled', deadline: isoInDays(1), budget_planned: 1000, budget_consumed: 999 })).toBe(false);
  });
  it('is safe on empty input', () => {
    expect(isAtRisk(null)).toBe(false);
  });
});

describe('fmtRelative', () => {
  // A fixed "now" so relative output is deterministic. The backend sends naive
  // UTC timestamps (no zone); fmtRelative treats them as UTC.
  const NOW = Date.parse('2026-07-22T12:00:00Z');
  const agoUtc = (secs) => new Date(NOW - secs * 1000).toISOString().replace('Z', '');

  it('says "just now" for very recent events', () => {
    expect(fmtRelative(agoUtc(5), NOW)).toBe('just now');
  });
  it('renders minutes and hours', () => {
    expect(fmtRelative(agoUtc(5 * 60), NOW)).toBe('5 minutes ago');
    expect(fmtRelative(agoUtc(2 * 3600), NOW)).toBe('2 hours ago');
  });
  it('renders days', () => {
    expect(fmtRelative(agoUtc(3 * 86400), NOW)).toBe('3 days ago');
  });
  it('treats a naive timestamp as UTC (no local-offset skew)', () => {
    // Exactly "now" in UTC -> just now, regardless of the test machine's zone.
    expect(fmtRelative('2026-07-22T12:00:00', NOW)).toBe('just now');
  });
  it('handles future timestamps and bad input', () => {
    expect(fmtRelative(new Date(NOW + 3600 * 1000).toISOString(), NOW)).toBe('in an hour');
    expect(fmtRelative(null, NOW)).toBe('—');
    expect(fmtRelative('not-a-date', NOW)).toBe('—');
  });
});

describe('fmtRelative — timezone correctness (regression)', () => {
  // The reported bug: a past event rendered as "in 5 hours" because a UTC instant
  // stored as +05:30 local was misparsed. Guard that a PAST instant is always
  // "ago", never "in", regardless of how the offset is expressed.
  const NOW = Date.parse('2026-07-24T00:00:00Z');
  const past = (secs) => new Date(NOW - secs * 1000);

  it('a past UTC (Z) timestamp never renders as future', () => {
    const out = fmtRelative(past(5 * 3600).toISOString(), NOW); // "...Z"
    expect(out).toBe('5 hours ago');
    expect(out).not.toMatch(/^in /);
  });

  it('a past instant expressed in a +05:30 offset (as the backend now sends) reads as ago', () => {
    // 2026-07-24T00:30:00+05:30 === 2026-07-23T19:00:00Z === 5h before NOW.
    // This is exactly the shape TIMESTAMPTZ now serializes; it must not be
    // misread as a naive local time and pushed into the future.
    const out = fmtRelative('2026-07-24T00:30:00+05:30', NOW);
    expect(out).toBe('5 hours ago');
    expect(out).not.toMatch(/^in /);
  });

  it('covers just now / minutes / hours / days', () => {
    expect(fmtRelative(past(5).toISOString(), NOW)).toBe('just now');
    expect(fmtRelative(past(5 * 60).toISOString(), NOW)).toBe('5 minutes ago');
    expect(fmtRelative(past(3 * 3600).toISOString(), NOW)).toBe('3 hours ago');
    expect(fmtRelative(past(2 * 86400).toISOString(), NOW)).toBe('2 days ago');
  });
});

describe('fmtRelativeOrDate', () => {
  const NOW = Date.parse('2026-07-24T00:00:00Z');
  const daysAgo = (n) => new Date(NOW - n * 86400000).toISOString();

  it('uses relative time within the last week', () => {
    expect(fmtRelativeOrDate(daysAgo(3), NOW)).toBe('3 days ago');
  });
  it('switches to an absolute date beyond ~7 days', () => {
    // Not "23 days ago" — an exact date instead.
    const out = fmtRelativeOrDate(daysAgo(23), NOW);
    expect(out).not.toMatch(/ago$/);
    expect(out).toMatch(/2026/);
  });
  it('is safe on empty input', () => {
    expect(fmtRelativeOrDate(null, NOW)).toBe('—');
  });
});

describe('fmtDateTime / fmtAbsDate', () => {
  it('formats a full timestamp as "D Mon YYYY, HH:MM" (24h)', () => {
    // 2026-07-23T09:02:00Z === 2026-07-23 09:02 UTC.
    expect(fmtDateTime('2026-07-23T09:02:00Z')).toMatch(/2026/);
    // 24-hour clock, no AM/PM.
    expect(fmtDateTime('2026-07-23T13:00:00Z')).not.toMatch(/[AP]M/i);
  });
  it('fmtAbsDate is date-only', () => {
    expect(fmtAbsDate('2026-07-23T09:02:00Z')).toMatch(/2026/);
    expect(fmtAbsDate('2026-07-23T09:02:00Z')).not.toMatch(/:/);
  });
  it('is safe on empty input', () => {
    expect(fmtDateTime(null)).toBe('—');
    expect(fmtAbsDate(null)).toBe('—');
  });
});
