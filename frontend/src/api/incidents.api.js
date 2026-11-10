import apiClient from './client';

export const incidentsApi = {
  list: async ({ projectId, status } = {}) => {
    return apiClient.get('/incidents/', {
      params: { project_id: projectId || undefined, status: status || undefined },
    });
  },

  create: async (data) => {
    return apiClient.post('/incidents/', data);
  },

  update: async (incidentId, data) => {
    return apiClient.patch(`/incidents/${incidentId}`, data);
  },
};
