import apiClient from './client';

export const activityApi = {
  getProjectFeed: async (projectId, limit = 50, skip = 0) => {
    return apiClient.get(`/activity/project/${projectId}`, { params: { limit, skip } });
  },

  getUserFeed: async (userId, limit = 50, skip = 0) => {
    return apiClient.get(`/activity/user/${userId}`, { params: { limit, skip } });
  },

  getMyFeed: async (limit = 50, skip = 0) => {
    return apiClient.get('/activity/me', { params: { limit, skip } });
  },

  getItemHistory: async (itemType, itemId) => {
    return apiClient.get(`/activity/item/${itemType}/${itemId}`);
  },
};
