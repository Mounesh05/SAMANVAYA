import apiClient from './client';

export const projectsApi = {
  list: async (orgId) => {
    return apiClient.get('/projects/', { params: orgId ? { org_id: orgId } : {} });
  },

  getById: async (projectId) => {
    return apiClient.get(`/projects/${projectId}`);
  },

  listByTeam: async (teamId) => {
    return apiClient.get(`/projects/team/${teamId}`);
  },

  create: async (data) => {
    return apiClient.post('/projects/', data);
  },

  // CR-013: project membership.
  listMembers: async (projectId) => apiClient.get(`/projects/${projectId}/members`),

  addMember: async (projectId, employeeId) =>
    apiClient.post(`/projects/${projectId}/members`, { employee_id: employeeId }),

  removeMember: async (projectId, employeeId) =>
    apiClient.delete(`/projects/${projectId}/members/${employeeId}`),
};
