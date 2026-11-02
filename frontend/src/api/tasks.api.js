import apiClient from './client';

export const tasksApi = {
  list: (params = {}) => apiClient.get('/api/tasks', { params }),
  get: (id) => apiClient.get(`/api/tasks/${id}`),
  create: (data) => apiClient.post('/api/tasks', data),
  update: (id, data) => apiClient.put(`/api/tasks/${id}`, data),
  updateStatus: (id, status) =>
    apiClient.patch(`/api/tasks/${id}/status`, { status }),
  delete: (id) => apiClient.delete(`/api/tasks/${id}`),
  assign: (id, employeeId) =>
    apiClient.patch(`/api/tasks/${id}/assign`, { assignee_id: employeeId }),
};
