import apiClient from './client';

export const employeesApi = {
  list: async (params = {}) => {
    return apiClient.get('/employees/', { params });
  },

  getById: async (employeeId) => {
    return apiClient.get(`/employees/${employeeId}`);
  },

  create: async (data) => {
    return apiClient.post('/employees/', data);
  },

  update: async (employeeId, updates) => {
    return apiClient.put(`/employees/${employeeId}`, updates);
  },

  delete: async (employeeId) => {
    return apiClient.delete(`/employees/${employeeId}`);
  },

  assignTeam: async (employeeId, teamId) => {
    return apiClient.post(`/employees/${employeeId}/assign-team`, { team_id: teamId });
  },
};
