import apiClient from './client';

export const githubApi = {
  // PR syncing & management
  getMyPRs: () => apiClient.get('/api/role/developer/my-prs'),
  getLeadReviewQueue: () => apiClient.get('/api/role/lead/review-queue'),
  syncPR: (data) => apiClient.post('/api/github/sync-pr', data),
  syncRepoPRs: (data) => apiClient.post('/api/github/sync-repository-prs', data),
  
  // Repositories
  listRepositories: (params = {}) => apiClient.get('/api/github/list-repositories', { params }),
  getRepositoryInfo: (owner, repo) => apiClient.get('/api/github/repository-info', { params: { owner, repo } }),
  getHealth: () => apiClient.get('/api/github/health'),

  // Backwards compatibility / mock fallback helpers
  getRepositories: (params = {}) => apiClient.get('/api/github/list-repositories', { params }),
  getPullRequests: (params = {}) => apiClient.get('/api/role/developer/my-prs', { params }),
  getPullRequest: (id) => apiClient.get(`/api/code-quality/pr/${id}`),
  getCommits: (params = {}) => apiClient.get('/api/github/commits', { params }),
};
