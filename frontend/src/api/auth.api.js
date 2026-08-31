import apiClient from './client';

export const authApi = {
  // Simple login with email + password
  login: async (credentials) => {
    return apiClient.post('/auth/login', credentials);
  },

  // Full login with employee_id + org password + emp password
  loginFull: async (credentials) => {
    return apiClient.post('/auth/login/full', credentials);
  },

  // Register new user
  register: async (userData) => {
    return apiClient.post('/auth/register', userData);
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
