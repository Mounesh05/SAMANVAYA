import apiClient from './client';

export const reportsApi = {
  list: (params = {}) => apiClient.get('/api/performance/reports', { params }),
  get: (id) => apiClient.get(`/api/performance/reports/${id}`),
  generate: (data) => apiClient.post('/api/performance/reports/generate', data),
  download: (id) =>
    apiClient.get(`/api/performance/reports/${id}/download`, {
      responseType: 'blob',
    }),
};
