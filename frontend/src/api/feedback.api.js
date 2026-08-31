import apiClient from './client';

export const feedbackApi = {
  submitPMFeedback: async (performanceId, data) => {
    return apiClient.post(`/performance/feedback/${performanceId}/pm`, data);
  },

  submitLeadFeedback: async (performanceId, data) => {
    return apiClient.post(`/performance/feedback/${performanceId}/lead`, data);
  },

  submitQAFeedback: async (performanceId, data) => {
    return apiClient.post(`/performance/feedback/${performanceId}/qa`, data);
  },

  submitDevOpsFeedback: async (performanceId, data) => {
    return apiClient.post(`/performance/feedback/${performanceId}/devops`, data);
  },

  submitCEOFeedback: async (performanceId, data) => {
    return apiClient.post(`/performance/feedback/${performanceId}/ceo`, data);
  },

  submitHRFeedback: async (performanceId, data) => {
    return apiClient.post(`/performance/feedback/${performanceId}/hr`, data);
  },
};
