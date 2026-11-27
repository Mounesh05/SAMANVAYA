import axios from 'axios';
import { useAuthStore } from '../store/useAuthStore';
import { API_BASE_URL } from '../utils/constants';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Request interceptor: attach token ─────────────────────────────────────

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

// ── Response interceptor: 401 auto-refresh ────────────────────────────────

let isRefreshing = false;
let failedQueue = [];

/**
 * Process the queue of requests that were waiting for a token refresh.
 * On success, retry each queued request with the new token.
 * On failure, reject them all so the UI can handle it.
 */
function processQueue(error, token = null) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(token);
    }
  });
  failedQueue = [];
}

// Errors keep their message as before and also carry the HTTP status
// (undefined when the server could not be reached), so pages such as sign-in
// can react to a status without parsing text.
// Validation errors (422) arrive as a list of { loc, msg }; turn them into
// one readable sentence instead of "[object Object]".
export function readableDetail(detail) {
  if (typeof detail?.code === 'string' && typeof detail.message === 'string') return detail.message;
  if (!Array.isArray(detail)) return typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : detail;
  return detail
    .map((item) => {
      if (typeof item === 'string') return item;
      const field = (item?.loc || []).filter((part) => part !== 'body').join(' ');
      const message = String(item?.msg || 'is not valid').replace(/^Value error, /, '');
      return field ? `${field}: ${message}` : message;
    })
    .join('; ');
}

function withStatus(err, status) {
  err.status = status;
  return err;
}

apiClient.interceptors.response.use(
  // Success: unwrap response.data as before
  (response) => response.data,

  // Error handler
  async (error) => {
    const originalRequest = error.config;
    const status = error?.response?.status;
    const detail = readableDetail(
      error?.response?.data?.detail || error?.response?.data?.message
    );

    // ── 401 Auto-Refresh Logic ──────────────────────────────────────────

    if (status === 401 && !originalRequest._retry) {
      // Don't try to refresh when the failing request IS the refresh call
      // or the login call (prevents infinite loops).
      const isAuthEndpoint =
        originalRequest.url?.includes('/auth/refresh') ||
        originalRequest.url?.includes('/auth/login');

      if (isAuthEndpoint) {
        localStorage.removeItem('samanvaya_token');
        localStorage.removeItem('samanvaya_user');
        if (window.location.pathname !== '/login') {
          window.location.assign('/login?expired=true');
        }
        return Promise.reject(
          withStatus(new Error(detail || 'Authentication failed'), status)
        );
      }

      // If a refresh is already in progress, queue this request
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((newToken) => {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return apiClient(originalRequest);
        });
      }

      // Mark that we're refreshing
      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Call the refresh endpoint with the current (possibly near-expired) token
        const currentToken = localStorage.getItem('samanvaya_token');
        const response = await axios.post(
          `${API_BASE_URL}/auth/refresh`,
          {},
          {
            headers: {
              Authorization: `Bearer ${currentToken}`,
              'Content-Type': 'application/json',
            },
          }
        );

        const newToken = response.data?.token;
        if (!newToken) {
          throw new Error('No token in refresh response');
        }

        // Persist the new token
        localStorage.setItem('samanvaya_token', newToken);

        // Keep the Zustand store in sync with the refreshed token.
        const state = useAuthStore.getState();
        if (state?.setAuth && state?.user) {
          state.setAuth(newToken, state.user);
        }

        // Process queued requests with the new token
        processQueue(null, newToken);

        // Retry the original request
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed — clear session and redirect to login
        processQueue(refreshError, null);
        localStorage.removeItem('samanvaya_token');
        localStorage.removeItem('samanvaya_user');
        if (window.location.pathname !== '/login') {
          window.location.assign('/login?expired=true');
        }
        return Promise.reject(
          new Error('Session expired. Please log in again.')
        );
      } finally {
        isRefreshing = false;
      }
    }

    // ── Non-401 errors ──────────────────────────────────────────────────

    const message = typeof detail === 'string' ? detail : status === 403
      ? 'You do not have permission for this action' : error?.message || 'An unexpected error occurred';
    const normalized = new Error(message);
    // Preserve status semantics without attaching Authorization headers, request
    // configuration, submitted private notes or structured validation input.
    if (status) normalized.response = { status, data: { detail: typeof detail === 'string' ? detail : undefined } };
    return Promise.reject(withStatus(normalized, status));
  }
);

export default apiClient;
