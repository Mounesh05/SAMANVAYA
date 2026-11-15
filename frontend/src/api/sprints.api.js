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

  // planning -> active -> completed (CREATE_SPRINT, project write access).
  changeStatus: async (sprintId, status) => {
    return apiClient.patch(`/sprints/${sprintId}/status`, { status });
  },
};
