/**
 * Client-side mirror of the backend RBAC matrix (backend/_shared/auth.py).
 *
 * Used purely to hide/disable UI the user can't act on — the backend remains
 * the source of truth and re-checks every request. Keep in sync with the server.
 */

export const ROLES = ['Viewer', 'Contributor', 'Manager', 'Admin'];

const PERMISSIONS = {
  Viewer: new Set(['read']),
  Contributor: new Set(['read', 'create', 'update']),
  Manager: new Set(['read', 'create', 'update', 'delete', 'view_activity']),
  Admin: new Set(['read', 'create', 'update', 'delete', 'manage_users', 'view_activity']),
};

export function can(role, action) {
  return PERMISSIONS[role]?.has(action) ?? false;
}

export function isAdmin(role) {
  return role === 'Admin';
}
