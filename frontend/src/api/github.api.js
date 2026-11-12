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

  listBranches: async (owner, repo) => {
    return apiClient.get('/github/branches', { params: { owner, repo } });
  },

  getProjectConfig: async (projectId) => {
    return apiClient.get(`/github/projects/${projectId}/config`);
  },

  saveProjectConfig: async (projectId, data) => {
    return apiClient.put(`/github/projects/${projectId}/config`, data);
  },

  syncPullRequest: async (data) => {
    return apiClient.post('/github/sync-pr', data);
  },

  // A project's pull requests, read only (CR-002: QA and DevOps).
  listProjectPullRequests: async (projectId) => {
    return apiClient.get(`/github/projects/${projectId}/pull-requests`);
  },

  syncRepositoryPRs: async (data) => {
    return apiClient.post('/github/sync-repository-prs', data);
  },

  provisionQaWorkflow: async (data) => {
    return apiClient.post('/github/provision-qa-workflow', data);
  },
};
