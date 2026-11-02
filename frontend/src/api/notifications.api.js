import apiClient from './client';

export const notificationsApi = {
  list: (params = {}) => apiClient.get('/api/notifications', { params }),
  markRead: (id) => apiClient.patch(`/api/notifications/${id}/read`),
  markAllRead: () => apiClient.patch('/api/notifications/mark-all-read'),
  getUnreadCount: () => apiClient.get('/api/notifications/unread-count'),
};
