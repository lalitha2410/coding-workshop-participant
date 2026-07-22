import { api } from './client';
import { qs } from './qs';

// Backend filters: project_id, status (+ limit, offset).
export const listDeliverables = (params) => api.get('deliverables', `/deliverables${qs(params)}`);
export const getDeliverable = (id) => api.get('deliverables', `/deliverables/${id}`);
export const createDeliverable = (data) => api.post('deliverables', '/deliverables', data);
export const updateDeliverable = (id, data) => api.put('deliverables', `/deliverables/${id}`, data);
export const deleteDeliverable = (id) => api.del('deliverables', `/deliverables/${id}`);

export const DELIVERABLE_STATUSES = ['not_started', 'in_progress', 'blocked', 'completed'];

// Dependencies: { deliverable_id, depends_on: [...], dependents: [...] }
export const getDependencies = (id) => api.get('deliverables', `/deliverables/${id}/dependencies`);
export const addDependency = (id, dependsOnId) =>
  api.post('deliverables', `/deliverables/${id}/dependencies`, { depends_on_id: dependsOnId });
export const removeDependency = (id, dependsOnId) =>
  api.del('deliverables', `/deliverables/${id}/dependencies/${dependsOnId}`);
