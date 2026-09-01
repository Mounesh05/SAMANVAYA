import apiClient from './client';
import { DEFAULT_ORG_ID } from '../utils/constants';

export const projectsApi = {
  list: async (orgId = DEFAULT_ORG_ID) => {
    return apiClient.get('/projects/', { params: { org_id: orgId } });
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
};
