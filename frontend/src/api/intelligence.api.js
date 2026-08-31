import apiClient from './client';

export const intelligenceApi = {
  analyzePR: async (prId, data) => {
    return apiClient.post(`/intelligence/analyze-pr/${prId}`, data);
  },

  analyzeSprint: async (sprintId, data = {}) => {
    return apiClient.post(`/intelligence/analyze-sprint/${sprintId}`, data);
  },

  analyzeDeployment: async (deploymentId, data) => {
    return apiClient.post(`/intelligence/analyze-deployment/${deploymentId}`, data);
  },

  checkHealth: async () => {
    return apiClient.get('/intelligence/health');
  },
};
