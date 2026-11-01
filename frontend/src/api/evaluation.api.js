import apiClient from './client';

export const evaluationApi = {
  evaluateDeveloperAI: async (data) => {
    return apiClient.post('/evaluation/evaluate', data, { timeout: 180000 });
  },
  getLatest: async () => {
    return apiClient.get('/evaluation/latest');
  },
  getById: async (evaluationId) => {
    return apiClient.get(`/evaluation/${evaluationId}`);
  },
  listByEmployee: async (employeeId) => {
    return apiClient.get(`/evaluation/employee/${employeeId}`);
  },
  listByPullRequest: async (owner, repo, prNumber) => {
    return apiClient.get(`/evaluation/repository/${owner}/${repo}/pr/${prNumber}`);
  },
};
