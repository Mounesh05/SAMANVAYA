import apiClient from './client';

export const teamsApi = {
  list: (params = {}) => apiClient.get('/api/teams', { params }),
  get: (id) => apiClient.get(`/api/teams/${id}`),
  create: (data) => apiClient.post('/api/teams', data),
  update: (id, data) => apiClient.put(`/api/teams/${id}`, data),
  delete: (id) => apiClient.delete(`/api/teams/${id}`),
  getMembers: (id) => apiClient.get(`/api/teams/${id}/members`),
  addMember: (id, employeeId) =>
    apiClient.post(`/api/teams/${id}/members`, { employee_id: employeeId }),
  removeMember: (id, employeeId) =>
    apiClient.delete(`/api/teams/${id}/members/${employeeId}`),
  assignLead: (id, leadId) =>
    apiClient.put(`/api/teams/${id}/lead`, { lead_id: leadId }),
};
