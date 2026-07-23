/**
 * Turn a raw activity_log entry into readable English.
 *
 *   summaryText(entry)  -> "Lalitha renamed user 'manager' to 'ram'"
 *                          "admin deleted project 'Apollo Platform Rebuild'"
 *   changeLines(entry)  -> ["Changed status from Active to On hold", ...]
 *
 * An entry is: { username, action, entity_type, entity_name, changes }
 * where changes is [{ field, old, new }] (null for creates/deletes).
 */

import { fmtDate } from './format';

// The field that holds an entity's display name (used to detect renames).
const NAME_FIELD = { user: 'username' };
function nameFieldFor(entityType) {
  return NAME_FIELD[entityType] || 'name';
}

// Friendlier labels for a few fields; otherwise the raw field name is humanized.
const FIELD_LABELS = {
  budget_planned: 'planned budget',
  budget_consumed: 'consumed budget',
  completion_pct: 'completion',
  allocation_pct: 'allocation',
  start_date: 'start date',
  end_date: 'end date',
  due_date: 'due date',
  project_id: 'project',
  depends_on_id: 'dependency',
};

export function fieldLabel(field) {
  return FIELD_LABELS[field] || String(field).replace(/_/g, ' ');
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}(T|$)/;
// A lowercase snake/word token like "active" or "on_hold" — safe to prettify.
const ENUM_TOKEN = /^[a-z][a-z0-9]*(_[a-z0-9]+)*$/;

/** Present a stored old/new value the way a person would read it. */
export function humanizeValue(value) {
  if (value === null || value === undefined || value === '') return 'nothing';
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'string' && ISO_DATE.test(value)) return fmtDate(value);
  if (typeof value === 'string' && ENUM_TOKEN.test(value)) {
    // lowercase enum tokens only: on_hold -> On hold, in_progress -> In progress.
    // Emails, names, and mixed-case text are left exactly as stored.
    const cleaned = value.replace(/_/g, ' ');
    return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
  }
  return String(value);
}

export function actorName(entry) {
  return entry.username || 'A former user';
}

const ACTION_VERB = { created: 'created', updated: 'updated', deleted: 'deleted' };

/** The one-line "who did what" sentence. */
export function summaryText(entry) {
  const who = actorName(entry);
  const type = entry.entity_type;
  const name = entry.entity_name || `#${entry.entity_id ?? '?'}`;

  if (entry.action === 'updated') {
    const rename = (entry.changes || []).find((c) => c.field === nameFieldFor(type));
    if (rename) {
      return `${who} renamed ${type} '${humanizeName(rename.old)}' to '${humanizeName(rename.new)}'`;
    }
    return `${who} updated ${type} '${name}'`;
  }

  const verb = ACTION_VERB[entry.action] || entry.action;
  return `${who} ${verb} ${type} '${name}'`;
}

function humanizeName(v) {
  return v === null || v === undefined || v === '' ? '(unnamed)' : String(v);
}

/**
 * Human-readable lines for each field-level change on an update. The name field
 * is skipped because the rename is already stated in summaryText().
 */
export function changeLines(entry) {
  if (entry.action !== 'updated' || !Array.isArray(entry.changes)) return [];
  const nameField = nameFieldFor(entry.entity_type);
  return entry.changes
    .filter((c) => c.field !== nameField)
    .map((c) => {
      const label = fieldLabel(c.field);
      const from = humanizeValue(c.old);
      const to = humanizeValue(c.new);
      if (from === 'nothing') return `Set ${label} to ${to}`;
      if (to === 'nothing') return `Cleared ${label}`;
      return `Changed ${label} from ${from} to ${to}`;
    });
}
