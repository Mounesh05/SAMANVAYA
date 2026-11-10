import apiClient from './client';

export const algorithmsApi = {
  getAvailability: () => apiClient.get('/algorithms/availability'),
  inspectStructure: (data) => apiClient.post('/algorithms/structure', data),
  getCompatibleHistory: (runId) => apiClient.get(
    `/algorithms/runs/${encodeURIComponent(runId)}/compatible-history`,
  ),
  // Preserve caller-owned contracts, datasets and resource limits. A non-null
  // contract selects generic mode; legacy sorting requests omit it.
  startRun: (data) => apiClient.post('/algorithms/runs', data),
  getRun: (runId) => apiClient.get(`/algorithms/runs/${encodeURIComponent(runId)}`),
  reevaluate: (runId, decisionPolicy) => apiClient.post(
    `/algorithms/runs/${encodeURIComponent(runId)}/reevaluate`, { decision_policy: decisionPolicy },
  ),
  getHistory: (projectId, limit = 10) => apiClient.get(
    `/algorithms/projects/${encodeURIComponent(projectId)}/history`,
    { params: { limit } },
  ),
  submitFeedback: (runId, data) => apiClient.post(
    `/algorithms/runs/${encodeURIComponent(runId)}/feedback`, data,
  ),
  getExplanation: (runId) => apiClient.post(
    `/algorithms/runs/${encodeURIComponent(runId)}/explanation`,
  ),
};
