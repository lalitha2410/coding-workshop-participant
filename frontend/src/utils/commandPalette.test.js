import { describe, it, expect } from 'vitest';
import {
  searchableTypes, quickNavActions, groupResults, flattenNavigable, moveHighlight, isNoResults,
} from './commandPalette';

describe('searchableTypes (RBAC)', () => {
  it('gives everyone the four core entities but not Users', () => {
    const t = searchableTypes('Viewer').map((x) => x.type);
    expect(t).toEqual(['project', 'deliverable', 'resource', 'allocation']);
  });
  it('adds Users only for Admins', () => {
    expect(searchableTypes('Admin').map((x) => x.type)).toContain('user');
    expect(searchableTypes('Manager').map((x) => x.type)).not.toContain('user');
  });
});

describe('quickNavActions (RBAC-filtered empty state)', () => {
  it('hides Activity and Users from a Viewer', () => {
    const routes = quickNavActions('Viewer').map((a) => a.route);
    expect(routes).toContain('/projects');
    expect(routes).not.toContain('/activity');
    expect(routes).not.toContain('/users');
  });
  it('shows Activity to a Manager but not Users', () => {
    const routes = quickNavActions('Manager').map((a) => a.route);
    expect(routes).toContain('/activity');
    expect(routes).not.toContain('/users');
  });
  it('shows everything to an Admin', () => {
    const routes = quickNavActions('Admin').map((a) => a.route);
    expect(routes).toContain('/activity');
    expect(routes).toContain('/users');
  });
});

const allowed = searchableTypes('Admin');

describe('groupResults', () => {
  it('orders groups by the canonical type order and keeps the labels', () => {
    const byType = {
      resource: { items: [{ id: 1 }], total: 1 },
      project: { items: [{ id: 2 }], total: 1 },
    };
    expect(groupResults(byType, allowed).map((g) => g.type)).toEqual(['project', 'resource']);
  });

  it('caps items per group and flags hasMore from the total', () => {
    const items = Array.from({ length: 6 }, (_, i) => ({ id: i }));
    const g = groupResults({ project: { items, total: 42 } }, allowed, 5)[0];
    expect(g.items).toHaveLength(5);
    expect(g.hasMore).toBe(true);
    expect(g.total).toBe(42);
  });

  it('drops empty successful groups but keeps errored ones (robustness)', () => {
    const byType = {
      project: { items: [], total: 0 },        // dropped
      deliverable: { error: true },            // kept, so the UI can flag it
      resource: { items: [{ id: 9 }], total: 1 },
    };
    const groups = groupResults(byType, allowed);
    const types = groups.map((g) => g.type);
    expect(types).toEqual(['deliverable', 'resource']);
    expect(groups.find((g) => g.type === 'deliverable').error).toBe(true);
  });

  it('isNoResults is true only when nothing (not even an error) survives', () => {
    expect(isNoResults(groupResults({ project: { items: [], total: 0 } }, allowed))).toBe(true);
    expect(isNoResults(groupResults({ project: { error: true } }, allowed))).toBe(false);
  });
});

describe('flattenNavigable', () => {
  it('flattens capped items across groups in order', () => {
    const groups = groupResults({
      project: { items: [{ id: 1 }, { id: 2 }], total: 2 },
      resource: { items: [{ id: 3 }], total: 1 },
    }, allowed);
    const flat = flattenNavigable(groups);
    expect(flat.map((f) => [f.type, f.item.id])).toEqual([
      ['project', 1], ['project', 2], ['resource', 3],
    ]);
  });
});

describe('moveHighlight (wrap-around keyboard nav)', () => {
  it('returns -1 for an empty list', () => {
    expect(moveHighlight(-1, 0, 1)).toBe(-1);
  });
  it('starts at the first item going down, last going up', () => {
    expect(moveHighlight(-1, 3, 1)).toBe(0);
    expect(moveHighlight(-1, 3, -1)).toBe(2);
  });
  it('moves and wraps in both directions', () => {
    expect(moveHighlight(0, 3, 1)).toBe(1);
    expect(moveHighlight(2, 3, 1)).toBe(0);   // wrap forward
    expect(moveHighlight(0, 3, -1)).toBe(2);  // wrap backward
  });
});
