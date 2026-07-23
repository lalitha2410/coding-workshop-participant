/**
 * Consistent toast phrasing for CRUD actions across the app.
 *
 * Records (Project/Deliverable/Resource/User):
 *   "<Entity> '<name>' <created|updated|deleted>"
 * Allocations (a link between a resource and a project, no single name):
 *   "Allocation for <resource> on <project> <created|updated|deleted>"
 * Dependencies (a deliverable's prerequisite edge):
 *   "Dependency on '<deliverable>' <added|removed>"
 */

export const entityMsg = (entity, name, action) => `${entity} '${name}' ${action}`;

export const allocationMsg = (resource, project, action) =>
  `Allocation for ${resource} on ${project} ${action}`;

export const dependencyMsg = (name, action) => `Dependency on '${name}' ${action}`;

// ---------------------------------------------------------------------------
// Update descriptions — say WHICH fields changed, not just "updated".
// ---------------------------------------------------------------------------

// Loose equality: treat null/undefined/'' as empty, and compare by string so
// 800000 (number), 800000.0 and "800000" all match. Handles the mixed shapes
// that flow from API rows vs. form payloads.
const _norm = (v) => (v === null || v === undefined || v === '' ? '' : String(v));
const _eq = (a, b) => _norm(a) === _norm(b);

/** Join field labels naturally: ["a"]→"a", ["a","b"]→"a and b", ["a","b","c"]→"a, b and c". */
export function joinLabels(labels) {
  if (!labels || labels.length === 0) return '';
  if (labels.length === 1) return labels[0];
  return `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}`;
}

/**
 * Describe what actually changed between `original` and `changes` for an update
 * toast. Returns { changed: boolean, message: string } — when `changed` is
 * false the caller should show an info toast ("No changes made").
 *
 * config:
 *   entity      lowercase noun, e.g. 'user'         (for "Renamed user '…'")
 *   possessive  'their' | 'its'                     (for "and updated <poss> <fields>")
 *   nameKey     key of the display-name field, or null if the entity has none
 *   subject     used as the "for …" target when nameKey is null (e.g. an allocation)
 *   fields      [{ key, label }] non-name fields to compare, in display order
 */
export function describeUpdate(original, changes, config) {
  const { entity, possessive = 'its', nameKey = null, subject, fields = [] } = config;
  const orig = original || {};
  const next = changes || {};

  let rename = null;
  let displayName;
  if (nameKey) {
    const oldName = orig[nameKey];
    const newName = nameKey in next ? next[nameKey] : oldName;
    displayName = newName ?? oldName;
    if (nameKey in next && !_eq(oldName, newName)) rename = { from: oldName, to: newName };
  }

  const changedLabels = [];
  for (const f of fields) {
    if (!(f.key in next)) continue;
    if (!_eq(orig[f.key], next[f.key])) changedLabels.push(f.label);
  }

  if (!rename && changedLabels.length === 0) {
    return { changed: false, message: 'No changes made' };
  }

  const fieldClause = joinLabels(changedLabels);
  const target = nameKey ? `'${displayName}'` : subject;

  if (rename && changedLabels.length === 0) {
    return { changed: true, message: `Renamed ${entity} '${rename.from}' to '${rename.to}'` };
  }
  if (rename) {
    return { changed: true, message: `Renamed ${entity} '${rename.from}' to '${rename.to}' and updated ${possessive} ${fieldClause}` };
  }
  return { changed: true, message: `Updated ${fieldClause} for ${target}` };
}
