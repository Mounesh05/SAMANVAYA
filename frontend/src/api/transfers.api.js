import apiClient from './client';

export const transfersApi = {
  // Create a new transfer request
  createTransfer: async (data) => {
    return apiClient.post('/transfers/', data);
  },

  // Get all transfer requests (filtered by role on backend)
  getTransfers: async (params = {}) => {
    return apiClient.get('/transfers/', { params });
  },

  // Get a specific transfer request by ID
  getTransferById: async (transferId) => {
    return apiClient.get(`/transfers/${transferId}`);
  },

  // Approve a transfer request (HR only)
  approveTransfer: async (transferId, data = {}) => {
    return apiClient.post(`/transfers/${transferId}/approve`, data);
  },

  // Reject a transfer request (HR only)
  rejectTransfer: async (transferId, data = {}) => {
    return apiClient.post(`/transfers/${transferId}/reject`, data);
  },

  // Flag a transfer request for review (Manager only)
  flagTransfer: async (transferId, data = {}) => {
    return apiClient.post(`/transfers/${transferId}/flag`, data);
  },

  // Execute an approved transfer (HR only)
  executeTransfer: async (transferId) => {
    return apiClient.post(`/transfers/${transferId}/execute`);
  },
};
