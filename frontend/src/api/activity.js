import { api } from './client';
import { qs } from './qs';

/**
 * Activity log / audit trail (hosted by the auth service at GET /auth/activity).
 * Manager+ only; the backend also hides entity_type='user' entries from Managers.
 * Returns the paginated {items,total,limit,offset} envelope, newest first.
 *
 * Filters: entity_type, action, user (a user id).
 */
export const listActivity = (params) => api.get('auth', `/auth/activity${qs(params)}`);

// Entity types and actions available as filters. 'user' is only meaningful to
// Admins (Managers never receive those rows), but listing it here is harmless.
export const ACTIVITY_ENTITY_TYPES = ['project', 'deliverable', 'resource', 'allocation', 'dependency', 'user'];
export const ACTIVITY_ACTIONS = ['created', 'updated', 'deleted'];
