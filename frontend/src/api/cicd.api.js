import apiClient from './client';

export const cicdApi = {
  /** POST /api/cicd-logs/analyze */
  analyzeLog: (data) => apiClient.post('/api/cicd-logs/analyze', data),

  /** POST /api/cicd-logs/analyze-file */
  analyzeFile: (formData) =>
    apiClient.post('/api/cicd-logs/analyze-file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  /** GET /api/cicd-logs/patterns */
  getFailurePatterns: () => apiClient.get('/api/cicd-logs/patterns'),

  /** Role endpoints */
  getDevOpsDashboard: () => apiClient.get('/api/role/devops/dashboard'),
  getPipelines: () => apiClient.get('/api/role/devops/pipelines'),
  getDeployments: () => apiClient.get('/api/role/devops/deployments'),
  getIncidents: () => apiClient.get('/api/devops/incidents'),
  createIncident: (data) => apiClient.post('/api/devops/incidents', data),
};
