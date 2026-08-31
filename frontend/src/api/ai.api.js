import apiClient from './client';

export const aiApi = {
  checkHealth: async () => {
    return apiClient.get('/ai/health');
  },

  invokeAgent: async (data) => {
    return apiClient.post('/ai/invoke', data);
  },
};
