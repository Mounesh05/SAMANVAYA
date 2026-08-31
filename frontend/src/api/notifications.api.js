import apiClient from './client';

export const notificationsApi = {
  list: async (limit = 50, skip = 0) => {
    return apiClient.get('/notifications/', { params: { limit, skip } });
  },

  getUnreadCount: async () => {
    return apiClient.get('/notifications/unread/count');
  },

  markRead: async (notificationId) => {
    return apiClient.patch(`/notifications/${notificationId}/read`);
  },

  markAllRead: async () => {
    return apiClient.patch('/notifications/read-all');
  },
};
