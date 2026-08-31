import apiClient from './client';

export const boardApi = {
  getSprintBoard: async (sprintId) => {
    return apiClient.get(`/boards/sprint/${sprintId}`);
  },

  getProjectBoard: async (projectId) => {
    return apiClient.get(`/boards/project/${projectId}`);
  },

  moveItem: async (itemId, itemType, targetStatus, reason = null) => {
    return apiClient.patch('/boards/move', {
      item_id: itemId,
      item_type: itemType, // 'task' | 'story'
      target_status: targetStatus,
      reason,
    });
  },
};
