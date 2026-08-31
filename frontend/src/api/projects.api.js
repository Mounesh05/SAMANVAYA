import apiClient from './client';

export const projectsApi = {
  list: async (orgId = 'ORG001') => {
    return apiClient.get('/projects/', { params: { org_id: orgId } });
  },

  getById: async (projectId) => {
    return apiClient.get(`/projects/${projectId}`);
  },

  listByTeam: async (teamId) => {
    return apiClient.get(`/projects/team/${teamId}`);
  },

  create: async (data) => {
    return apiClient.post('/projects/', data);
  },
};
