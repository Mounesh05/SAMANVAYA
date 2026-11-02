import apiClient from './client';

export const evaluationApi = {
  listEvaluations: (params = {}) =>
    apiClient.get('/api/evaluation', { params }),
  getEvaluation: (employeeId, params = {}) =>
    apiClient.get(`/api/evaluation/${employeeId}`, { params }),
  triggerEvaluation: (data) => apiClient.post('/api/evaluation/run', data),
  getHistory: (employeeId, params = {}) =>
    apiClient.get(`/api/evaluation/${employeeId}/history`, { params }),
  getStatus: (taskId) => apiClient.get(`/api/evaluation/status/${taskId}`),
  getHealth: () => apiClient.get('/api/evaluation/health'),
};
