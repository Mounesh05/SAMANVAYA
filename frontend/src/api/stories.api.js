import apiClient from './client';

export const storiesApi = {
  list: (params = {}) => apiClient.get('/api/stories', { params }),
  get: (id) => apiClient.get(`/api/stories/${id}`),
  create: (data) => apiClient.post('/api/stories', data),
  update: (id, data) => apiClient.put(`/api/stories/${id}`, data),
  delete: (id) => apiClient.delete(`/api/stories/${id}`),
};
