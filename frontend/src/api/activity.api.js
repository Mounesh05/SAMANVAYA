import apiClient from './client';

export const activityApi = {
  list: (params = {}) => apiClient.get('/api/activity', { params }),
  getForEntity: (entityType, entityId) =>
    apiClient.get('/api/activity', { params: { entity_type: entityType, entity_id: entityId } }),
};
