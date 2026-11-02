import apiClient from './client';

export const authApi = {
  /** POST /api/auth/login — email + password */
  login: (email, password) =>
    apiClient.post('/api/auth/login', { email, password }),

  /** POST /api/auth/logout */
  logout: () => apiClient.post('/api/auth/logout'),

  /** GET /api/auth/me */
  me: () => apiClient.get('/api/auth/me'),

  /** POST /api/auth/refresh */
  refresh: () => apiClient.post('/api/auth/refresh'),

  /** POST /api/auth/register */
  register: (data) => apiClient.post('/api/auth/register', data),
};
