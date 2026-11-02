import apiClient from './client';

export const feedbackApi = {
  list: (params = {}) => apiClient.get('/api/performance/feedback', { params }),
  submit: (data) => apiClient.post('/api/performance/feedback', data),
  get: (id) => apiClient.get(`/api/performance/feedback/${id}`),
  update: (id, data) => apiClient.put(`/api/performance/feedback/${id}`, data),
};
