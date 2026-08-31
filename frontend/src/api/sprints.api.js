import apiClient from './client';

export const sprintsApi = {
  create: async (data) => {
    return apiClient.post('/sprints/', data);
  },

  getById: async (sprintId) => {
    return apiClient.get(`/sprints/${sprintId}`);
  },

  listByProject: async (projectId) => {
    return apiClient.get(`/sprints/project/${projectId}`);
  },

  getActive: async (projectId) => {
    return apiClient.get(`/sprints/project/${projectId}/active`);
  },

  getHealth: async (sprintId) => {
    return apiClient.get(`/sprints/${sprintId}/health`);
  },
};
