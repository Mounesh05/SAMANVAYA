import apiClient from './client';

export const githubApi = {
  checkHealth: async () => {
    return apiClient.get('/github/health');
  },

  getRepositoryInfo: async (owner, repo) => {
    return apiClient.get('/github/repository-info', { params: { owner, repo } });
  },

  listRepositories: async (org = null) => {
    return apiClient.get('/github/list-repositories', { params: org ? { org } : {} });
  },

  syncPullRequest: async (data) => {
    return apiClient.post('/github/sync-pr', data);
  },

  syncRepositoryPRs: async (data) => {
    return apiClient.post('/github/sync-repository-prs', data);
  },
};
