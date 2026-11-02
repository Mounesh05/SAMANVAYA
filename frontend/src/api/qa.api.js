import apiClient from './client';

export const qaApi = {
  getDashboard: () => apiClient.get('/api/role/qa/dashboard'),
  getTestHealth: () => apiClient.get('/api/role/qa/test-health'),
  getBugs: () => apiClient.get('/api/role/qa/bugs'),
};
