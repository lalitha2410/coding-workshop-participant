import { describe, it, expect } from 'vitest';
import { summaryText, changeLines, humanizeValue, fieldLabel, actorName } from './activityText';

describe('summaryText', () => {
  it('describes a create', () => {
    const e = { username: 'admin', action: 'created', entity_type: 'project', entity_id: 7, entity_name: 'Apollo Platform Rebuild' };
    expect(summaryText(e)).toBe("admin created project 'Apollo Platform Rebuild'");
  });

  it('describes a delete', () => {
    const e = { username: 'admin', action: 'deleted', entity_type: 'project', entity_id: 7, entity_name: 'Apollo Platform Rebuild' };
    expect(summaryText(e)).toBe("admin deleted project 'Apollo Platform Rebuild'");
  });

  it('describes a plain update', () => {
    const e = { username: 'admin', action: 'updated', entity_type: 'project', entity_id: 7, entity_name: 'Apollo',
      changes: [{ field: 'status', old: 'active', new: 'on_hold' }] };
    expect(summaryText(e)).toBe("admin updated project 'Apollo'");
  });

  it('special-cases a user rename (username field)', () => {
    const e = { username: 'Lalitha', action: 'updated', entity_type: 'user', entity_id: 3, entity_name: 'ram',
      changes: [{ field: 'username', old: 'manager', new: 'ram' }] };
    expect(summaryText(e)).toBe("Lalitha renamed user 'manager' to 'ram'");
  });

  it('special-cases a project rename (name field)', () => {
    const e = { username: 'admin', action: 'updated', entity_type: 'project', entity_id: 1, entity_name: 'Zeus',
      changes: [{ field: 'name', old: 'Apollo', new: 'Zeus' }] };
    expect(summaryText(e)).toBe("admin renamed project 'Apollo' to 'Zeus'");
  });

  it('falls back to a placeholder actor for a former (deleted) user', () => {
    const e = { username: null, action: 'created', entity_type: 'resource', entity_id: 2, entity_name: 'Marcus' };
    expect(summaryText(e)).toBe("A former user created resource 'Marcus'");
  });

  it('falls back to an id when the entity name is missing', () => {
    const e = { username: 'admin', action: 'deleted', entity_type: 'allocation', entity_id: 9, entity_name: null };
    expect(summaryText(e)).toBe("admin deleted allocation '#9'");
  });
});

describe('changeLines', () => {
  it('renders a readable field change with humanized enum values', () => {
    const e = { action: 'updated', entity_type: 'project', changes: [{ field: 'status', old: 'active', new: 'on_hold' }] };
    expect(changeLines(e)).toEqual(['Changed status from Active to On hold']);
  });

  it('omits the name field (already stated in the summary) and keeps the rest', () => {
    const e = { action: 'updated', entity_type: 'user',
      changes: [{ field: 'username', old: 'a', new: 'b' }, { field: 'email', old: 'a@x', new: 'b@x' }] };
    expect(changeLines(e)).toEqual(['Changed email from a@x to b@x']);
  });

  it('phrases set / clear for empty sides', () => {
    const e = { action: 'updated', entity_type: 'project',
      changes: [{ field: 'deadline', old: null, new: '2026-09-01' }, { field: 'department', old: 'QA', new: null }] };
    const lines = changeLines(e);
    expect(lines[0]).toMatch(/^Set deadline to /);
    expect(lines[1]).toBe('Cleared department');
  });

  it('uses friendly field labels', () => {
    const e = { action: 'updated', entity_type: 'allocation', changes: [{ field: 'allocation_pct', old: 40, new: 75 }] };
    expect(changeLines(e)).toEqual(['Changed allocation from 40 to 75']);
  });

  it('returns nothing for creates and deletes', () => {
    expect(changeLines({ action: 'created', entity_type: 'project', changes: null })).toEqual([]);
    expect(changeLines({ action: 'deleted', entity_type: 'project', changes: null })).toEqual([]);
  });
});

describe('humanizeValue', () => {
  it('humanizes enum tokens, booleans, dates and empties', () => {
    expect(humanizeValue('in_progress')).toBe('In progress');
    expect(humanizeValue(true)).toBe('yes');
    expect(humanizeValue('2026-09-01')).toMatch(/2026/);
    expect(humanizeValue(null)).toBe('nothing');
    expect(humanizeValue('')).toBe('nothing');
  });
});

describe('fieldLabel / actorName', () => {
  it('maps known fields and humanizes unknown ones', () => {
    expect(fieldLabel('budget_planned')).toBe('planned budget');
    expect(fieldLabel('some_new_field')).toBe('some new field');
  });
  it('names the actor or a placeholder', () => {
    expect(actorName({ username: 'ada' })).toBe('ada');
    expect(actorName({ username: null })).toBe('A former user');
  });
});
