import apiClient from './client';

export const evaluationApi = {
  evaluateDeveloperAI: async (data) => {
    return apiClient.post('/evaluation/evaluate', data);
  },
};
