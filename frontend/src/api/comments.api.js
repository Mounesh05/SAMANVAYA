import apiClient from './client';

export const commentsApi = {
  add: async (parentType, parentId, body) => {
    return apiClient.post('/comments/', {
      parent_type: parentType,
      parent_id: parentId,
      body,
    });
  },

  list: async (parentType, parentId) => {
    return apiClient.get(`/comments/${parentType}/${parentId}`);
  },

  edit: async (commentId, body) => {
    return apiClient.put(`/comments/${commentId}`, { body });
  },

  delete: async (commentId) => {
    return apiClient.delete(`/comments/${commentId}`);
  },
};
