import apiClient from './client';

export const tasksApi = {
  create: async (data) => {
    return apiClient.post('/tasks/', data);
  },

  getById: async (taskId) => {
    return apiClient.get(`/tasks/${taskId}`);
  },

  listByProject: async (projectId) => {
    return apiClient.get(`/tasks/project/${projectId}`);
  },

  listByAssignee: async (assigneeId) => {
    return apiClient.get(`/tasks/assignee/${assigneeId}`);
  },

  listByStory: async (storyId) => {
    return apiClient.get(`/tasks/story/${storyId}`);
  },

  updateStatus: async (taskId, status) => {
    return apiClient.patch(`/tasks/${taskId}/status`, null, { params: { status } });
  },

  transition: async (taskId, status, reason = null) => {
    return apiClient.patch(`/tasks/${taskId}/transition`, { status, reason });
  },

  getAvailableTransitions: async (taskId) => {
    return apiClient.get(`/tasks/${taskId}/transitions`);
  },

  getHistory: async (taskId) => {
    return apiClient.get(`/tasks/${taskId}/history`);
  },
};
