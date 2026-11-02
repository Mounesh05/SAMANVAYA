import apiClient from './client';

export const boardApi = {
  get: (params = {}) => apiClient.get('/api/boards', { params }),
  moveTask: (taskId, status) =>
    apiClient.patch(`/api/tasks/${taskId}/status`, { status }),
};
