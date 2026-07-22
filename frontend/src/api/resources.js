import { api } from './client';
import { qs } from './qs';

// Backend filter: search (matches name or title) (+ limit, offset).
export const listResources = (params) => api.get('resources', `/resources${qs(params)}`);
export const getResource = (id) => api.get('resources', `/resources/${id}`);
export const createResource = (data) => api.post('resources', '/resources', data);
export const updateResource = (id, data) => api.put('resources', `/resources/${id}`, data);
export const deleteResource = (id) => api.del('resources', `/resources/${id}`);
