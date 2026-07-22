import { api } from './client';
import { qs } from './qs';

// Backend filters: project_id, status (+ limit, offset).
export const listDeliverables = (params) => api.get('deliverables', `/deliverables${qs(params)}`);
export const getDeliverable = (id) => api.get('deliverables', `/deliverables/${id}`);
export const createDeliverable = (data) => api.post('deliverables', '/deliverables', data);
export const updateDeliverable = (id, data) => api.put('deliverables', `/deliverables/${id}`, data);
export const deleteDeliverable = (id) => api.del('deliverables', `/deliverables/${id}`);

export const DELIVERABLE_STATUSES = ['not_started', 'in_progress', 'blocked', 'completed'];
