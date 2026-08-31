import apiClient from './client';

export const performanceApi = {
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
    return apiClient.post('/performance/evaluate', data);
  },

  // Trigger bulk evaluation (Admin)
  evaluateBulk: async (data) => {
    return apiClient.post('/performance/evaluate/bulk', data);
  },
};
