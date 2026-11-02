import apiClient from './client';

export const employeesApi = {
  list: (params = {}) => apiClient.get('/api/employees', { params }),
  get: (id) => apiClient.get(`/api/employees/${id}`),
  create: (data) => apiClient.post('/api/employees', data),
  update: (id, data) => apiClient.put(`/api/employees/${id}`, data),
  deactivate: (id) => apiClient.delete(`/api/employees/${id}`),
  assignTeam: (id, teamId) =>
    apiClient.post(`/api/employees/${id}/assign-team`, { team_id: teamId }),
};
