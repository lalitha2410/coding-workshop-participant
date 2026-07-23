/**
 * Pure logic for the command palette: which entity types the current role may
 * search, how raw per-type responses become ordered/capped groups, the flat
 * navigable list that lets arrow keys cross group boundaries, and the highlight
 * mover. Kept free of React/DOM so it can be unit tested directly.
 */

import { can } from '../auth/roles';

// Searchable entity types, in display order. `permission` mirrors the nav's
// visibility rules — Users are Admin-only; the rest are any authenticated role.
export const SEARCH_TYPES = [
  { type: 'project', label: 'Projects', route: '/projects', permission: 'read' },
  { type: 'deliverable', label: 'Deliverables', route: '/deliverables', permission: 'read' },
  { type: 'resource', label: 'Resources', route: '/resources', permission: 'read' },
  { type: 'allocation', label: 'Allocations', route: '/allocations', permission: 'read' },
  { type: 'user', label: 'Users', route: '/users', permission: 'manage_users' },
];

// Empty-state quick navigation, filtered by role (no Users below Admin; no
// Activity below Manager).
const NAV_ACTIONS = [
  { label: 'Go to Dashboard', route: '/' },
  { label: 'Go to Projects', route: '/projects' },
  { label: 'Go to Deliverables', route: '/deliverables' },
  { label: 'Go to Resources', route: '/resources' },
  { label: 'Go to Allocations', route: '/allocations' },
  { label: 'Go to Activity', route: '/activity', permission: 'view_activity' },
  { label: 'Go to Users', route: '/users', permission: 'manage_users' },
];

/** The entity-type configs the given role is allowed to search. */
export function searchableTypes(role) {
  return SEARCH_TYPES.filter((t) => can(role, t.permission));
}

/** Quick-nav actions for the empty state, filtered by role. */
export function quickNavActions(role) {
  return NAV_ACTIONS.filter((a) => !a.permission || can(role, a.permission));
}

/**
 * Fold raw per-type responses into ordered, capped groups.
 *
 * `byType` maps type -> { items, total } | { error: true }. Successful groups
 * with no items are dropped; errored groups are kept (so the UI can show a
 * per-group error without blanking the rest). `hasMore` drives the "See all"
 * link.
 */
export function groupResults(byType, allowed, perGroup = 5) {
  const groups = [];
  for (const cfg of allowed) {
    const res = byType[cfg.type];
    if (!res) continue;
    if (res.error) {
      groups.push({ ...cfg, items: [], total: 0, hasMore: false, error: true });
      continue;
    }
    const items = res.items || [];
    if (items.length === 0) continue;
    const total = res.total ?? items.length;
    groups.push({ ...cfg, items: items.slice(0, perGroup), total, hasMore: total > perGroup, error: false });
  }
  return groups;
}

/** True when a query ran, every allowed group is empty, and none errored. */
export function isNoResults(groups) {
  return groups.length === 0;
}

/**
 * Flatten the visible (capped) result items across all groups into one ordered
 * list, so ↑/↓ move continuously across group boundaries. Each entry keeps its
 * type/route and the raw row.
 */
export function flattenNavigable(groups) {
  return groups.flatMap((g) => g.items.map((item) => ({ type: g.type, route: g.route, item })));
}

/**
 * Move the highlighted index by `delta`, wrapping around. Returns -1 for an
 * empty list; starting from -1 lands on the first (down) or last (up) item.
 */
export function moveHighlight(index, length, delta) {
  if (length <= 0) return -1;
  if (index < 0) return delta > 0 ? 0 : length - 1;
  return (index + delta + length) % length;
}
