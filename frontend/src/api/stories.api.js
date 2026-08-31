import apiClient from './client';

export const storiesApi = {
  create: async (data) => {
    return apiClient.post('/stories/', data);
  },

  getById: async (storyId) => {
    return apiClient.get(`/stories/${storyId}`);
  },

  listBySprint: async (sprintId) => {
    return apiClient.get(`/stories/sprint/${sprintId}`);
  },

  listByAssignee: async (assigneeId) => {
    return apiClient.get(`/stories/assignee/${assigneeId}`);
  },

  updateStatus: async (storyId, status) => {
    return apiClient.patch(`/stories/${storyId}/status`, null, { params: { status } });
  },
};
