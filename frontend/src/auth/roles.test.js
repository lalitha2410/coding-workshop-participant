import { describe, it, expect } from 'vitest';
import { can, isAdmin, ROLES } from './roles';

describe('can() — RBAC matrix (mirrors backend/_shared/auth.py)', () => {
  it('lists the four roles', () => {
    expect(ROLES).toEqual(['Viewer', 'Contributor', 'Manager', 'Admin']);
  });

  it.each([
    ['Viewer', 'read', true],
    ['Viewer', 'create', false],
    ['Viewer', 'update', false],
    ['Viewer', 'delete', false],
    ['Contributor', 'read', true],
    ['Contributor', 'create', true],
    ['Contributor', 'update', true],
    ['Contributor', 'delete', false],
    ['Manager', 'delete', true],
    ['Manager', 'manage_users', false],
    ['Admin', 'delete', true],
    ['Admin', 'manage_users', true],
  ])('can(%s, %s) === %s', (role, action, expected) => {
    expect(can(role, action)).toBe(expected);
  });

  it('denies unknown roles and unknown actions', () => {
    expect(can('Wizard', 'read')).toBe(false);
    expect(can('Viewer', 'bogus')).toBe(false);
    expect(can(null, 'read')).toBe(false);
    expect(can(undefined, undefined)).toBe(false);
  });
});

describe('isAdmin()', () => {
  it('is true only for Admin', () => {
    expect(isAdmin('Admin')).toBe(true);
    expect(isAdmin('Manager')).toBe(false);
    expect(isAdmin('Viewer')).toBe(false);
    expect(isAdmin(null)).toBe(false);
  });
});
