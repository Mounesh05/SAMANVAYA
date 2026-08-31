import apiClient from './client';

export const codeQualityApi = {
  startAnalysis: async (data) => {
    return apiClient.post('/code-quality/analyze', data);
  },

  getRun: async (runId) => {
    return apiClient.get(`/code-quality/runs/${runId}`);
  },

  getRunFindings: async (runId, params = {}) => {
    return apiClient.get(`/code-quality/runs/${runId}/findings`, { params });
  },

  getLatestRun: async (repositoryId) => {
    return apiClient.get(`/code-quality/repositories/${repositoryId}/latest`);
  },

  getHistory: async (repositoryId, limit = 20) => {
    return apiClient.get(`/code-quality/repositories/${repositoryId}/history`, {
      params: { limit },
    });
  },
};
