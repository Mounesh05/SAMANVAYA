import axios from 'axios';
import { useAuthStore } from '../store/useAuthStore';

// VITE_API_URL should include /api, e.g. https://api.example.com/api.
// The legacy VITE_API_BASE_URL is supported. Same-origin /api works with Nginx.
const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  '/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('samanvaya_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error) => Promise.reject(error)
);

let isRefreshing = false;
let failedQueue = [];

function processQueue(error, token = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve(token);
  });
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const originalRequest = error.config;
    const status = error?.response?.status;
    const detail = error?.response?.data?.detail || error?.response?.data?.message;

    if (status === 401 && originalRequest && !originalRequest._retry) {
      const url = originalRequest.url || '';
      const isAuthEndpoint = url.includes('/auth/refresh') || url.includes('/auth/login');

      if (isAuthEndpoint) {
        localStorage.removeItem('samanvaya_token');
        localStorage.removeItem('samanvaya_user');
        if (window.location.pathname !== '/login') window.location.assign('/login?expired=true');
        return Promise.reject(new Error(detail || 'Authentication failed'));
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => failedQueue.push({ resolve, reject }))
          .then((newToken) => {
            originalRequest.headers = originalRequest.headers || {};
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            return apiClient(originalRequest);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;
      try {
        const currentToken = localStorage.getItem('samanvaya_token');
        const response = await axios.post(
          `${API_BASE_URL}/auth/refresh`,
          {},
          { headers: { Authorization: `Bearer ${currentToken}`, 'Content-Type': 'application/json' } }
        );
        const newToken = response.data?.token;
        if (!newToken) throw new Error('No token in refresh response');

        localStorage.setItem('samanvaya_token', newToken);
        const state = useAuthStore.getState();
        if (state?.setAuth && state?.user) state.setAuth(newToken, state.user);

        processQueue(null, newToken);
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem('samanvaya_token');
        localStorage.removeItem('samanvaya_user');
        if (window.location.pathname !== '/login') window.location.assign('/login?expired=true');
        return Promise.reject(new Error('Session expired. Please log in again.'));
      } finally {
        isRefreshing = false;
      }
    }

    if (status === 403) {
      return Promise.reject(new Error(detail || 'You do not have permission for this action'));
    }
    return Promise.reject(new Error(detail || error?.message || 'An unexpected error occurred'));
  }
);

export default apiClient;
