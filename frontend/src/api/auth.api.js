import apiClient from './client';

export const authApi = {
  // CR-016: one sign-in rule. { identifier (employee ID or work email),
  // organisation_password, employee_password }; both passwords are checked.
  login: async (credentials) => {
    return apiClient.post('/auth/login', credentials);
  },

  // Register new user
  register: async (userData) => {
    return apiClient.post('/auth/register', userData);
  },

  // First-run setup: the Chief Executive and the platform administrator.
  initializeFirstAccounts: async (setupData) => {
    return apiClient.post('/setup/initialize', setupData);
  },

  // Current authenticated user profile
  getMe: async () => {
    return apiClient.get('/auth/me');
  },

  // Refresh token
  refreshToken: async () => {
    return apiClient.post('/auth/refresh');
  },

  // Logout
  logout: async () => {
    try {
      await apiClient.post('/auth/logout');
    } catch {
      // Ignore backend logout errors
    } finally {
      localStorage.removeItem('samanvaya_token');
      localStorage.removeItem('samanvaya_user');
    }
  },
};
