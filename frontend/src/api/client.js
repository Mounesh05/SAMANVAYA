import axios from 'axios';
import { useAuthStore } from '../store/useAuthStore';
import { API_BASE_URL } from '../utils/constants';

// SEC-05: the session lives in an HttpOnly cookie that page scripts cannot
// read. Requests send it automatically; state-changing requests echo the
// readable CSRF cookie in X-CSRF-Token (double-submit).
const CSRF_COOKIE = 'samanvaya_csrf';
const SAFE_METHODS = ['get', 'head', 'options'];

export function csrfToken() {
  const entry = document.cookie.split('; ').find((part) => part.startsWith(`${CSRF_COOKIE}=`));
  return entry ? decodeURIComponent(entry.slice(CSRF_COOKIE.length + 1)) : '';
}

function withCsrf(config) {
  const method = (config.method || 'get').toLowerCase();
  const token = csrfToken();
  if (!SAFE_METHODS.includes(method) && token) {
    config.headers = config.headers || {};
    config.headers['X-CSRF-Token'] = token;
  }
  return config;
}

// Tokens from older versions are no longer kept in browser storage.
localStorage.removeItem('samanvaya_token');

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Request interceptor: CSRF header for cookie sessions ──────────────────

apiClient.interceptors.request.use(withCsrf, (error) => Promise.reject(error));

// ── Response interceptor: 401 auto-refresh ────────────────────────────────

let isRefreshing = false;
let failedQueue = [];

/**
 * Process the queue of requests that were waiting for a token refresh.
 * On success, retry each queued request with the new token.
 * On failure, reject them all so the UI can handle it.
 */
function processQueue(error) {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve();
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
        }).then(() => apiClient(originalRequest));
      }

      // Mark that we're refreshing
      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // The server rotates the session cookie; no token reaches page scripts.
        await axios.post(`${API_BASE_URL}/auth/refresh`, {},
          withCsrf({ method: 'post', withCredentials: true, headers: { 'Content-Type': 'application/json' } }));

        processQueue(null);
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed — clear session and redirect to login
        processQueue(refreshError);
        useAuthStore.getState()?.logout?.();
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
