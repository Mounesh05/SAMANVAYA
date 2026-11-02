import apiClient from './client';

export const codeQualityApi = {
  getSummary: (params = {}) => apiClient.get('/api/code-quality', { params }),
  getRepository: (id) => apiClient.get(`/api/code-quality/repositories/${id}`),
  getPR: (id) => apiClient.get(`/api/code-quality/pr/${id}`),
  getRun: (id) => apiClient.get(`/api/code-quality/runs/${id}`),
  getFindings: (params = {}) =>
    apiClient.get('/api/code-quality/findings', { params }),
  triggerAnalysis: (data) => apiClient.post('/api/code-quality/analyze', data),
};
