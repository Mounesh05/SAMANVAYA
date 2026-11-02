import apiClient from './client';

export const performanceApi = {
  /** GET /api/performance/:employee_id */
  getDeveloperPerformance: (employeeId) =>
    apiClient.get(`/api/performance/${employeeId}`),

  /** GET /api/performance/:employee_id/history */
  getHistory: (employeeId, params = {}) =>
    apiClient.get(`/api/performance/${employeeId}/history`, { params }),

  /** POST /api/performance/evaluate */
  triggerEvaluation: (data) => apiClient.post('/api/performance/evaluate', data),

  /** POST /api/performance/evaluate/bulk */
  bulkEvaluate: (data) => apiClient.post('/api/performance/evaluate/bulk', data),

  /** GET /api/role/developer/dashboard */
  getDeveloperDashboard: () =>
    apiClient.get('/api/role/developer/dashboard'),

  /** GET /api/role/lead/dashboard */
  getLeadDashboard: () => apiClient.get('/api/role/lead/dashboard'),

  /** GET /api/role/pm/dashboard */
  getPMDashboard: () => apiClient.get('/api/role/pm/dashboard'),

  /** GET /api/role/qa/dashboard */
  getQADashboard: () => apiClient.get('/api/role/qa/dashboard'),

  /** GET /api/role/devops/dashboard */
  getDevOpsDashboard: () => apiClient.get('/api/role/devops/dashboard'),

  /** GET /api/role/hr/dashboard */
  getHRDashboard: () => apiClient.get('/api/role/hr/dashboard'),

  /** GET /api/role/ceo/dashboard */
  getCEODashboard: () => apiClient.get('/api/role/ceo/dashboard'),

  /** GET /api/role/lead/team */
  getLeadTeam: () => apiClient.get('/api/role/lead/team'),

  /** GET /api/role/hr/organization */
  getOrganization: () => apiClient.get('/api/role/hr/organization'),

  /** CEO specific endpoints */
  getCEOExecutionHealth: (orgId = 'org-default') =>
    apiClient.get('/api/role/ceo/execution-health', { params: { org_id: orgId } }),

  getCEOCriticalRisks: (orgId = 'org-default') =>
    apiClient.get('/api/role/ceo/critical-risks', { params: { org_id: orgId } }),
};
