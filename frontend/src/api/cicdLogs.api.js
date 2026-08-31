import apiClient from './client';

export const cicdLogsApi = {
  analyzeLog: async (data) => {
    return apiClient.post('/cicd-logs/analyze', data);
  },
};
