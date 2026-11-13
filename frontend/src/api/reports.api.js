import apiClient from './client';

/** CR-011: report downloads. The backend checks export and view rights. */
export const reportsApi = {
  // Reports the caller may download: [{ type, title }].
  list: async () => apiClient.get('/reports'),

  // Returns a Blob with the CSV. `purpose` is required and kept in the audit log.
  downloadCsv: async (type, { purpose, projectId, from, to } = {}) =>
    apiClient.post(
      `/reports/${type}`,
      { purpose, project_id: projectId || null, from: from || null, to: to || null, format: 'csv' },
      { responseType: 'blob' },
    ),
};
