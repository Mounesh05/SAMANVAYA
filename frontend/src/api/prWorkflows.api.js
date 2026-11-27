import apiClient from './client';

const root = '/ai/workflows/v1';
export const prWorkflowsApi = {
  projects: (signal) => apiClient.get(`${root}/projects`, { signal }),
  start: (request) => apiClient.post(`${root}/pr-analysis`, request),
  importActionsResults: (projectId, request) => apiClient.post(`/qa/projects/${encodeURIComponent(projectId)}/import-actions-results`, request),
  status: (id, signal) => apiClient.get(`${root}/jobs/${encodeURIComponent(id)}`, { signal }),
  cancel: (id) => apiClient.post(`${root}/jobs/${encodeURIComponent(id)}/cancel`),
  report: (id, signal) => apiClient.get(`${root}/jobs/${encodeURIComponent(id)}/report`, { signal }),
  lookupReport: (params, signal) => apiClient.get(`${root}/pr-analysis/report`, { params, signal }),
};
