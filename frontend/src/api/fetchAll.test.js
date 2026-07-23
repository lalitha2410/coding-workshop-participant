import { describe, it, expect, vi } from 'vitest';
import { fetchAllRows } from './fetchAll';

// A fake paginated endpoint over `data`, honoring limit/offset and echoing filters.
function makeListFn(data) {
  return vi.fn(async ({ limit, offset }) => ({
    items: data.slice(offset, offset + limit),
    total: data.length,
    limit,
    offset,
  }));
}

describe('fetchAllRows', () => {
  it('returns a single page unchanged when total <= page size', async () => {
    const data = Array.from({ length: 12 }, (_, i) => ({ id: i + 1 }));
    const listFn = makeListFn(data);
    const rows = await fetchAllRows(listFn);
    expect(rows).toHaveLength(12);
    expect(listFn).toHaveBeenCalledTimes(1);
    expect(listFn).toHaveBeenCalledWith({ limit: 200, offset: 0 });
  });

  it('pages through everything beyond the 200-row cap', async () => {
    const data = Array.from({ length: 450 }, (_, i) => ({ id: i + 1 }));
    const listFn = makeListFn(data);
    const rows = await fetchAllRows(listFn);
    expect(rows).toHaveLength(450);
    expect(rows.map((r) => r.id)).toEqual(data.map((r) => r.id)); // order + completeness
    expect(listFn).toHaveBeenCalledTimes(3); // ceil(450/200)
    expect(listFn.mock.calls.map((c) => c[0].offset)).toEqual([0, 200, 400]);
  });

  it('forwards filters on every page request', async () => {
    const data = Array.from({ length: 250 }, (_, i) => ({ id: i + 1 }));
    const listFn = makeListFn(data);
    await fetchAllRows(listFn, { status: 'active', department: 'Engineering' });
    for (const call of listFn.mock.calls) {
      expect(call[0]).toMatchObject({ status: 'active', department: 'Engineering' });
    }
  });

  it('returns [] for an empty result set', async () => {
    const listFn = makeListFn([]);
    expect(await fetchAllRows(listFn)).toEqual([]);
    expect(listFn).toHaveBeenCalledTimes(1);
  });

  it('stops safely if a page comes back empty despite an inflated total', async () => {
    // total claims 1000 but only 50 rows exist -> must not loop forever.
    const listFn = vi.fn(async ({ offset }) => ({
      items: offset < 50 ? [{ id: offset }] : [],
      total: 1000,
    }));
    const rows = await fetchAllRows(listFn);
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.length).toBeLessThan(1000); // did not spin
  });
});
