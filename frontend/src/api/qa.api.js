import apiClient from './client';

export const qaApi = {
  getProjects: () => apiClient.get('/qa/projects'),
  getDashboard: (projectId) =>
    apiClient.get('/qa/dashboard', { params: projectId ? { project_id: projectId } : {} }),
  getSuites: (projectId) => apiClient.get('/qa/suites', { params: { project_id: projectId } }),
  createSuite: (data) => apiClient.post('/qa/suites', data),
  updateSuite: (suiteId, data) => apiClient.patch(`/qa/suites/${suiteId}`, data),
  getCases: (projectId, filters = {}) =>
    apiClient.get('/qa/cases', { params: { project_id: projectId, ...filters } }),
  createCase: (data) => apiClient.post('/qa/cases', data),
  updateCase: (caseId, data) => apiClient.patch(`/qa/cases/${caseId}`, data),
  cloneCase: (caseId) => apiClient.post(`/qa/cases/${caseId}/clone`),
  getExecutions: (caseId) => apiClient.get(`/qa/cases/${caseId}/executions`),
  createExecution: (caseId, data) =>
    apiClient.post(`/qa/cases/${caseId}/executions`, data),
  getDefects: (projectId, filters = {}) =>
    apiClient.get('/qa/defects', { params: { ...(projectId ? { project_id: projectId } : {}), ...filters } }),
  createDefect: (data) => apiClient.post('/qa/defects', data),
  getDefect: (defectId) => apiClient.get(`/qa/defects/${defectId}`),
  updateDefect: (defectId, data) => apiClient.patch(`/qa/defects/${defectId}`, data),
  
  // CI Integration
  enableCIIntegration: (projectId, repository, branch = 'main') =>
    apiClient.post(`/qa/projects/${projectId}/enable-ci`, { repository, branch }),
  getCIConfigs: (projectId, branch = null) => 
    apiClient.get(`/qa/projects/${projectId}/ci-config`, { params: branch ? { branch } : {} }),
  disableCIIntegration: (projectId, branch) => 
    apiClient.delete(`/qa/projects/${projectId}/ci-config`, { params: { branch } }),
  getTestRuns: (projectId, filters = {}) =>
    apiClient.get('/qa/test-runs', { params: { project_id: projectId, ...filters } }),
};
