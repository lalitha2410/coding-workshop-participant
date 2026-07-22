import { api } from './client';
import { qs } from './qs';

// Backend filters: status, department (+ limit, offset). Returns {items,total,limit,offset}.
export const listProjects = (params) => api.get('projects', `/projects${qs(params)}`);
export const getProject = (id) => api.get('projects', `/projects/${id}`);
export const createProject = (data) => api.post('projects', '/projects', data);
export const updateProject = (id, data) => api.put('projects', `/projects/${id}`, data);
export const deleteProject = (id) => api.del('projects', `/projects/${id}`);

export const PROJECT_STATUSES = ['planning', 'active', 'on_hold', 'completed', 'cancelled'];
export const DEPARTMENTS = ['Engineering', 'Data', 'Marketing', 'Design', 'Operations', 'Finance'];
