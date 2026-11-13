import apiClient from './client';

/** CR-010: two-person approval for account changes. */
export const approvalsApi = {
  // Requests waiting for the caller's decision (never their own).
  listPending: async () => apiClient.get('/approvals/pending'),

  // Requests the caller raised that are still pending.
  listMine: async () => apiClient.get('/approvals/mine'),

  approve: async (approvalId, comment = null) =>
    apiClient.post(`/approvals/${approvalId}/approve`, { comment }),

  reject: async (approvalId, reason) =>
    apiClient.post(`/approvals/${approvalId}/reject`, { reason }),
};
