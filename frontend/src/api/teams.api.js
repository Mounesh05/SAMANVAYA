import apiClient from './client';

export const teamsApi = {
  list: async (params = {}) => {
    return apiClient.get('/teams/', { params });
  },

  getById: async (teamId) => {
    return apiClient.get(`/teams/${teamId}`);
  },

  getMembers: async (teamId) => {
    return apiClient.get(`/teams/${teamId}/members`);
  },

  create: async (data) => {
    return apiClient.post('/teams/', data);
  },

  update: async (teamId, updates) => {
    return apiClient.put(`/teams/${teamId}`, updates);
  },
};
