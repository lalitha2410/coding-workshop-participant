/**
 * Bulk-action execution over the existing single-item endpoints.
 *
 * We deliberately loop the per-item API calls rather than add bulk endpoints:
 * each call is independently authorized and audit-logged by the backend, so a
 * bulk delete of 5 rows produces 5 activity entries — and partial failure is a
 * natural outcome we report honestly.
 */

/** `2 projects` / `1 project` — count with a correctly pluralized noun. */
export function pluralize(n, singular) {
  return `${n} ${n === 1 ? singular : `${singular}s`}`;
}

/** A short, human reason for a single failed item, derived from its ApiError. */
export function failureReason(error) {
  if (!error) return 'Unknown error';
  switch (error.status) {
    case 401: return 'Session expired';
    case 403: return 'Not permitted';
    case 404: return 'Already gone';
    default: return error.message || 'Request failed';
  }
}

/** Fold raw per-item results into a summary the UI can render. */
export function summarizeBulk(results) {
  const failures = results
    .filter((r) => !r.ok)
    .map((r) => ({
      item: r.item,
      status: r.error?.status ?? null,
      message: failureReason(r.error),
    }));
  return {
    total: results.length,
    succeeded: results.length - failures.length,
    failed: failures.length,
    failures,
    ok: failures.length === 0,
  };
}

/**
 * Run `op` against every item, sequentially, catching per-item errors so one
 * failure never aborts the batch. Reports progress after each item. Resolves to
 * a summarizeBulk() result.
 */
export async function runBulk(items, op, { onProgress } = {}) {
  const results = [];
  for (let i = 0; i < items.length; i += 1) {
    const item = items[i];
    try {
      await op(item);
      results.push({ item, ok: true });
    } catch (error) {
      results.push({ item, ok: false, error });
    }
    if (onProgress) onProgress(i + 1, items.length);
  }
  return summarizeBulk(results);
}

/**
 * One-line outcome text.
 *   all ok:   "5 projects deleted."
 *   partial:  "3 projects deleted, 2 failed."
 */
export function bulkSummaryText(summary, singular, verbPast) {
  if (summary.failed === 0) return `${pluralize(summary.total, singular)} ${verbPast}.`;
  return `${pluralize(summary.succeeded, singular)} ${verbPast}, ${summary.failed} failed.`;
}
