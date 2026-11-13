import apiClient from './client';

export const incidentsApi = {
  // Incidents the caller may see (all in accessible projects, or own reports).
  list: async (params = {}) => {
    return apiClient.get('/incidents/', { params });
  },

  // Report an incident (CREATE_INCIDENT).
  report: async (data) => {
    return apiClient.post('/incidents/', data);
  },

  // CR-014: one incident (owner, timeline, resolution).
  get: async (incidentId) => apiClient.get(`/incidents/${incidentId}`),

  // CR-014: triage (TRIAGE_INCIDENT: DevOps, Lead, PM). Send only what changes.
  triage: async (incidentId, changes) => apiClient.patch(`/incidents/${incidentId}`, changes),
};
