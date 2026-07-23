import { describe, it, expect } from 'vitest';
import { describeUpdate, joinLabels } from './messages';

const userCfg = {
  entity: 'user', possessive: 'their', nameKey: 'username',
  fields: [{ key: 'email', label: 'email' }],
};
const projectCfg = {
  entity: 'project', possessive: 'its', nameKey: 'name',
  fields: [
    { key: 'status', label: 'status' },
    { key: 'deadline', label: 'deadline' },
    { key: 'budget_planned', label: 'planned budget' },
  ],
};

describe('joinLabels', () => {
  it('joins naturally', () => {
    expect(joinLabels([])).toBe('');
    expect(joinLabels(['email'])).toBe('email');
    expect(joinLabels(['status', 'deadline'])).toBe('status and deadline');
    expect(joinLabels(['status', 'deadline', 'planned budget'])).toBe('status, deadline and planned budget');
  });
});

describe('describeUpdate', () => {
  it('single field changed', () => {
    const r = describeUpdate({ username: 'ram', email: 'a@x' }, { username: 'ram', email: 'b@x' }, userCfg);
    expect(r).toEqual({ changed: true, message: "Updated email for 'ram'" });
  });

  it('multiple fields changed (name unchanged)', () => {
    const orig = { name: 'Apollo', status: 'active', deadline: '2026-09-01', budget_planned: 800000 };
    const next = { name: 'Apollo', status: 'on_hold', deadline: '2026-10-01', budget_planned: 800000 };
    expect(describeUpdate(orig, next, projectCfg).message).toBe("Updated status and deadline for 'Apollo'");
  });

  it('three fields join with a comma and "and"', () => {
    const orig = { name: 'Apollo', status: 'active', deadline: '2026-09-01', budget_planned: 800000 };
    const next = { name: 'Apollo', status: 'on_hold', deadline: '2026-10-01', budget_planned: 900000 };
    expect(describeUpdate(orig, next, projectCfg).message).toBe("Updated status, deadline and planned budget for 'Apollo'");
  });

  it('rename only', () => {
    const r = describeUpdate({ username: 'manager', email: 'a@x' }, { username: 'ram', email: 'a@x' }, userCfg);
    expect(r).toEqual({ changed: true, message: "Renamed user 'manager' to 'ram'" });
  });

  it('rename + other fields (with possessive)', () => {
    const r = describeUpdate({ username: 'manager', email: 'a@x' }, { username: 'ram', email: 'b@x' }, userCfg);
    expect(r.message).toBe("Renamed user 'manager' to 'ram' and updated their email");
  });

  it('rename + fields uses the entity possessive ("its")', () => {
    const r = describeUpdate({ name: 'Apollo', status: 'active' }, { name: 'Zeus', status: 'on_hold' }, projectCfg);
    expect(r.message).toBe("Renamed project 'Apollo' to 'Zeus' and updated its status");
  });

  it('no changes -> info message', () => {
    const r = describeUpdate({ username: 'ram', email: 'a@x' }, { username: 'ram', email: 'a@x' }, userCfg);
    expect(r).toEqual({ changed: false, message: 'No changes made' });
  });

  it('treats 800000, 800000.0 and empty/null equivalently (no false positives)', () => {
    const orig = { name: 'Apollo', budget_planned: 800000.0, deadline: null, status: 'active' };
    const next = { name: 'Apollo', budget_planned: 800000, deadline: '', status: 'active' };
    expect(describeUpdate(orig, next, projectCfg).changed).toBe(false);
  });

  it('supports name-less entities via a subject (allocations)', () => {
    const cfg = { entity: 'allocation', nameKey: null, subject: 'Marcus Reed on Apollo', fields: [{ key: 'allocation_pct', label: 'allocation %' }] };
    const r = describeUpdate({ allocation_pct: 70 }, { allocation_pct: 90 }, cfg);
    expect(r.message).toBe('Updated allocation % for Marcus Reed on Apollo');
  });
});
