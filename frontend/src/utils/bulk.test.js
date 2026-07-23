import { describe, it, expect } from 'vitest';
import { pluralize, failureReason, summarizeBulk, runBulk, bulkSummaryText } from './bulk';

// Minimal stand-in for ApiError (status + message).
const apiErr = (status, message) => ({ status, message });

describe('pluralize', () => {
  it('singular vs plural', () => {
    expect(pluralize(1, 'project')).toBe('1 project');
    expect(pluralize(0, 'project')).toBe('0 projects');
    expect(pluralize(5, 'project')).toBe('5 projects');
  });
});

describe('failureReason', () => {
  it('maps well-known statuses to friendly text', () => {
    expect(failureReason(apiErr(403))).toBe('Not permitted');
    expect(failureReason(apiErr(404))).toBe('Already gone');
    expect(failureReason(apiErr(401))).toBe('Session expired');
  });
  it('falls back to the backend message for other errors (e.g. FK constraint)', () => {
    expect(failureReason(apiErr(400, 'row is still referenced'))).toBe('row is still referenced');
  });
  it('is safe on a missing/blank error', () => {
    expect(failureReason(null)).toBe('Unknown error');
    expect(failureReason(apiErr(500))).toBe('Request failed');
  });
});

describe('summarizeBulk', () => {
  it('summarises an all-success batch', () => {
    const s = summarizeBulk([{ item: { id: 1 }, ok: true }, { item: { id: 2 }, ok: true }]);
    expect(s).toMatchObject({ total: 2, succeeded: 2, failed: 0, ok: true });
    expect(s.failures).toEqual([]);
  });

  it('captures each failure with its status and reason', () => {
    const s = summarizeBulk([
      { item: { id: 1 }, ok: true },
      { item: { id: 2 }, ok: false, error: apiErr(403) },
      { item: { id: 3 }, ok: false, error: apiErr(400, 'FK constraint') },
    ]);
    expect(s).toMatchObject({ total: 3, succeeded: 1, failed: 2, ok: false });
    expect(s.failures).toEqual([
      { item: { id: 2 }, status: 403, message: 'Not permitted' },
      { item: { id: 3 }, status: 400, message: 'FK constraint' },
    ]);
  });
});

describe('runBulk', () => {
  it('runs every item, isolates failures, and reports progress', async () => {
    const items = [{ id: 1 }, { id: 2 }, { id: 3 }, { id: 4 }];
    const progress = [];
    // ids 2 and 4 fail; the batch keeps going regardless.
    const op = (item) => (item.id % 2 === 0
      ? Promise.reject(apiErr(item.id === 2 ? 403 : 404))
      : Promise.resolve());

    const summary = await runBulk(items, op, { onProgress: (done, total) => progress.push([done, total]) });

    expect(summary).toMatchObject({ total: 4, succeeded: 2, failed: 2, ok: false });
    expect(summary.failures.map((f) => f.item.id)).toEqual([2, 4]);
    expect(summary.failures.map((f) => f.message)).toEqual(['Not permitted', 'Already gone']);
    // Progress ticks once per item, in order.
    expect(progress).toEqual([[1, 4], [2, 4], [3, 4], [4, 4]]);
  });

  it('handles an empty selection', async () => {
    const summary = await runBulk([], () => Promise.resolve());
    expect(summary).toMatchObject({ total: 0, succeeded: 0, failed: 0, ok: true });
  });
});

describe('bulkSummaryText', () => {
  it('states full success', () => {
    expect(bulkSummaryText({ total: 5, succeeded: 5, failed: 0 }, 'project', 'deleted'))
      .toBe('5 projects deleted.');
  });
  it('states partial failure honestly', () => {
    expect(bulkSummaryText({ total: 5, succeeded: 3, failed: 2 }, 'project', 'deleted'))
      .toBe('3 projects deleted, 2 failed.');
  });
  it('handles a total wipeout', () => {
    expect(bulkSummaryText({ total: 2, succeeded: 0, failed: 2 }, 'user', 'deleted'))
      .toBe('0 users deleted, 2 failed.');
  });
});
