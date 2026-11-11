import apiClient from './client';

export const algorithmsApi = {
  getPRIntelligence: params => apiClient.get('/algorithms/pr-intelligence', { params }),
  discoverRequirements: body => apiClient.post('/algorithms/requirements/discover', body),
  proposeRequirementSource: body => apiClient.post('/algorithms/requirements/sources', body),
  getRequirementSources: projectId => apiClient.get(`/algorithms/projects/${encodeURIComponent(projectId)}/requirement-sources`),
  approveRequirementSource: (id, body) => apiClient.post(`/algorithms/requirements/sources/${encodeURIComponent(id)}/approve`, body),
  proposeContract: (body) => apiClient.post('/algorithms/contracts', body),
  getContract: (id) => apiClient.get(`/algorithms/contracts/${encodeURIComponent(id)}`),
  getContracts: (projectId) => apiClient.get(`/algorithms/projects/${encodeURIComponent(projectId)}/contracts`),
  approveContract: (id, body) => apiClient.post(`/algorithms/contracts/${encodeURIComponent(id)}/approve`, body),
  startCompatibility: (body) => apiClient.post('/algorithms/compatibility/runs', body),
  getRelationships: (params) => apiClient.get('/algorithms/compatibility/relationships', { params }),
  getFunctionCompatibility: (projectId, functionId) => apiClient.get(
    `/algorithms/compatibility/functions/${encodeURIComponent(functionId)}/history`, { params: { project_id: projectId } },
  ),
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
