import apiClient from './client';

export const sprintsApi = {
  list: (params = {}) => apiClient.get('/api/sprints', { params }),
  get: (id) => apiClient.get(`/api/sprints/${id}`),
  create: (data) => apiClient.post('/api/sprints', data),
  update: (id, data) => apiClient.put(`/api/sprints/${id}`, data),
  delete: (id) => apiClient.delete(`/api/sprints/${id}`),
  getActive: (projectId) =>
    apiClient.get('/api/sprints', { params: { project_id: projectId, status: 'active' } }),
};
