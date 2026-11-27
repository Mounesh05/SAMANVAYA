import apiClient from './client';

const base = (project) => `/projects/${encodeURIComponent(project)}/releases`;
const path = (project, release) => `${base(project)}/${encodeURIComponent(release)}`;

export const releasesApi = {
  list: (project, params, signal) => apiClient.get(base(project), { params, signal }),
  get: (project, release, signal) => apiClient.get(path(project, release), { signal }),
  history: (project, release, params, signal) => apiClient.get(`${path(project, release)}/history`, { params, signal }),
  create: (project, data) => apiClient.post(base(project), data),
  initializeBaseline: (project, data) => apiClient.post(`${base(project)}/baseline`, data),
  act: (project, release, data) => apiClient.post(`${path(project, release)}/actions`, data),
};
