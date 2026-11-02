/**
 * Samanvaya — Axios HTTP client
 * Central HTTP transport layer. Attach JWT, intercept 401/403.
 */
import axios from 'axios';

// If VITE_API_URL is explicitly set to an absolute URL (e.g. https://...ngrok-free.app), use it.
// Otherwise, default to empty string '' so Vite's dev proxy handles /api, or 'http://localhost:8000'.
const envApiUrl = import.meta.env.VITE_API_URL;
const BASE_URL = envApiUrl !== undefined ? envApiUrl : 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
  },
});

/** Attach Bearer token to every request if present in localStorage */
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('samanvaya_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/** Normalise errors. On 401 clear token and redirect to /login. */
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('samanvaya_token');
      localStorage.removeItem('samanvaya_user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    // Normalise error message
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An unexpected error occurred';
    error.userMessage = message;
    return Promise.reject(error);
  }
);

export default apiClient;
