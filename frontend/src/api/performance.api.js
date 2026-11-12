import apiClient from './client';

export const performanceApi = {
  getReadiness: () => apiClient.get('/performance/readiness'),
  getAssessments: (id) => apiClient.get(`/performance/developer/${encodeURIComponent(id)}/assessments`),
  getAssessmentHistory: (id) => apiClient.get(`/performance/assessments/${encodeURIComponent(id)}/history`),
  replayAssessment: (id, revision) => apiClient.get(`/performance/assessments/${encodeURIComponent(id)}/revisions/${revision}/replay`),
  appealAssessment: (id, data) => apiClient.post(`/performance/assessments/${encodeURIComponent(id)}/appeals`, data),
  getAssignments: () => apiClient.get('/performance/human-assignments'),
  getHumanReview: (id) => apiClient.get(`/performance/human-reviews/${encodeURIComponent(id)}`).catch((error) => {
    if (error.response?.status === 404) return null;
    throw error;
  }),
  submitHumanReview: (id, data) => apiClient.post(`/performance/human-reviews/${encodeURIComponent(id)}`, data),
  reviseHumanReview: (id, data) => apiClient.post(`/performance/human-reviews/${encodeURIComponent(id)}/revisions`, data),
  // Main Dashboard endpoint for developer
  getDeveloperDashboard: async (developerId, periods = 6) => {
    return apiClient.get(`/performance/dashboard/${developerId}`, {
      params: { periods },
    });
  },

  // Detailed performance evaluation data
  getDeveloperPerformance: async (developerId, periodLabel = null) => {
    return apiClient.get(`/performance/developer/${developerId}`, {
      params: periodLabel ? { period_label: periodLabel } : {},
    });
  },

  // Historical trend
  getPerformanceTrend: async (developerId, limit = 10) => {
    return apiClient.get(`/performance/developer/${developerId}/trend`, {
      params: { limit },
    });
  },

  // Team performance
  getTeamPerformance: async (projectId = 'all', periodLabel = 'current') => {
    return apiClient.get(`/performance/team/${projectId}/${periodLabel}`);
  },

  // Trigger single evaluation (CEO/Admin)
  evaluateDeveloper: async (data) => {
    return apiClient.post('/performance/evaluate', data, { timeout: 120000 });
  },

  // Trigger bulk evaluation (Admin)
  evaluateBulk: async (data) => {
    return apiClient.post('/performance/evaluate/bulk', data);
  },

  // Human evaluation policy
  getHumanEvaluationPolicy: async () => {
    return apiClient.get('/performance/policy');
  },

  configureHumanEvaluationPolicy: async (data) => {
    return apiClient.post('/performance/policy', data);
  },

  getHumanEvaluationPolicyHistory: async (limit = 10) => {
    return apiClient.get('/performance/policy/history', { params: { limit } });
  },
};
