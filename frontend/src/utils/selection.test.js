import { describe, it, expect } from 'vitest';
import { pageSelectableIds, toggleId, toggleAll, selectionSummary } from './selection';

const rows = [{ id: 1 }, { id: 2 }, { id: 3 }];

describe('pageSelectableIds', () => {
  it('returns every id when there is no predicate', () => {
    expect(pageSelectableIds(rows)).toEqual([1, 2, 3]);
  });
  it('filters out non-selectable rows (e.g. your own user)', () => {
    expect(pageSelectableIds(rows, (r) => r.id !== 2)).toEqual([1, 3]);
  });
});

describe('toggleId', () => {
  it('adds an id that is not present', () => {
    expect([...toggleId(new Set([1]), 2)]).toEqual([1, 2]);
  });
  it('removes an id that is present', () => {
    expect([...toggleId(new Set([1, 2]), 2)]).toEqual([1]);
  });
  it('does not mutate the input set', () => {
    const src = new Set([1]);
    toggleId(src, 2);
    expect([...src]).toEqual([1]);
  });
});

describe('toggleAll', () => {
  it('selects all page ids when none/some are selected', () => {
    expect([...toggleAll(new Set(), [1, 2, 3])]).toEqual([1, 2, 3]);
    expect([...toggleAll(new Set([2]), [1, 2, 3])]).toEqual([2, 1, 3]);
  });
  it('clears the page when all are already selected', () => {
    expect([...toggleAll(new Set([1, 2, 3]), [1, 2, 3])]).toEqual([]);
  });
  it('only touches the page ids, leaving off-page selection intact', () => {
    // 9 is not on this page; it must survive a page-level toggle.
    expect([...toggleAll(new Set([9]), [1, 2])].sort()).toEqual([1, 2, 9]);
  });
});

describe('selectionSummary', () => {
  it('reports none selected', () => {
    expect(selectionSummary(new Set(), [1, 2, 3])).toEqual({ count: 0, allSelected: false, someSelected: false });
  });
  it('reports a partial (indeterminate) selection', () => {
    expect(selectionSummary(new Set([2]), [1, 2, 3])).toEqual({ count: 1, allSelected: false, someSelected: true });
  });
  it('reports a full-page selection', () => {
    expect(selectionSummary(new Set([1, 2, 3]), [1, 2, 3])).toEqual({ count: 3, allSelected: true, someSelected: false });
  });
  it('is never "all selected" on an empty page', () => {
    expect(selectionSummary(new Set(), [])).toEqual({ count: 0, allSelected: false, someSelected: false });
  });
  it('counts only ids present on this page', () => {
    // 9 is selected but off-page; it must not count toward the page summary.
    expect(selectionSummary(new Set([1, 9]), [1, 2, 3])).toEqual({ count: 1, allSelected: false, someSelected: true });
  });
});
