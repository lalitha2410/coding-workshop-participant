import { api } from './client';
import { qs } from './qs';

// Admin-only user management (auth service). List is paginated + ?search.
export const listUsers = (params) => api.get('auth', `/auth/users${qs(params)}`);
// Create reuses POST /auth/register (elevated roles require the admin's token,
// which the client attaches automatically). Update is username/email only.
export const createUser = (data) => api.post('auth', '/auth/register', data);
export const updateUser = (id, data) => api.put('auth', `/auth/users/${id}`, data);
export const changeUserRole = (id, role) => api.put('auth', `/auth/users/${id}/role`, { role });
export const deleteUser = (id) => api.del('auth', `/auth/users/${id}`);

export const ROLE_OPTIONS = ['Viewer', 'Contributor', 'Manager', 'Admin'];
