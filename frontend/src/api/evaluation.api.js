import apiClient from './client';

// Must exceed the backend model timeout plus evidence collection (default 180s).
const EVALUATION_TIMEOUT_MS = Number(import.meta.env.VITE_AI_EVALUATION_TIMEOUT_MS) || 180000;

export const evaluationApi = {
  evaluateDeveloperAI: async (data) => {
    return apiClient.post('/evaluation/evaluate', data, { timeout: EVALUATION_TIMEOUT_MS });
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
