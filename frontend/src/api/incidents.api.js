import apiClient from './client';

export const incidentsApi = {
  // Incidents the caller may see (all in accessible projects, or own reports).
  list: async (params = {}) => {
    return apiClient.get('/incidents/', { params });
  },

  // Report an incident (CREATE_INCIDENT). Triage is DevOps work (CR-003).
  report: async (data) => {
    return apiClient.post('/incidents/', data);
  },
};
