import { api } from './client';
import { qs } from './qs';

// Backend filters: resource_id, project_id (+ limit, offset).
export const listAllocations = (params) => api.get('allocations', `/allocations${qs(params)}`);
export const getAllocation = (id) => api.get('allocations', `/allocations/${id}`);
export const createAllocation = (data) => api.post('allocations', '/allocations', data);
export const updateAllocation = (id, data) => api.put('allocations', `/allocations/${id}`, data);
export const deleteAllocation = (id) => api.del('allocations', `/allocations/${id}`);

// Analytics endpoints (reads → any authenticated role).
export const overAllocated = () => api.get('allocations', '/allocations/over-allocated');
export const allocationSummary = () => api.get('allocations', '/allocations/summary');
