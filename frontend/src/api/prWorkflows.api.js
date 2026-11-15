import apiClient from './client';

const root = '/ai/workflows/v1';
export const prWorkflowsApi = {
  projects: (signal) => apiClient.get(`${root}/projects`, { signal }),
  start: (request) => apiClient.post(`${root}/pr-analysis`, request),
  status: (id, signal) => apiClient.get(`${root}/jobs/${encodeURIComponent(id)}`, { signal }),
  report: (id, signal) => apiClient.get(`${root}/jobs/${encodeURIComponent(id)}/report`, { signal }),
};
