import apiClient from './client';

export const projectsApi = {
  list: (params = {}) => apiClient.get('/api/projects', { params }),
  get: (id) => apiClient.get(`/api/projects/${id}`),
  create: (data) => apiClient.post('/api/projects', data),
  update: (id, data) => apiClient.put(`/api/projects/${id}`, data),
  delete: (id) => apiClient.delete(`/api/projects/${id}`),
  getMembers: (id) => apiClient.get(`/api/projects/${id}/members`),
  addMember: (id, employeeId) =>
    apiClient.post(`/api/projects/${id}/members`, { employee_id: employeeId }),
  removeMember: (id, employeeId) =>
    apiClient.delete(`/api/projects/${id}/members/${employeeId}`),
};
