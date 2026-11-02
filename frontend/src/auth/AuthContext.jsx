/**
 * AuthContext — central authentication state
 * Provides: user, role, token, login(), logout(), loading
 */
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authApi } from '../api/auth.api';

const AuthContext = createContext(null);

const TOKEN_KEY = 'samanvaya_token';
const USER_KEY = 'samanvaya_user';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  /** Restore session from localStorage on mount */
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    const cachedUser = localStorage.getItem(USER_KEY);
    if (token && cachedUser) {
      try {
        setUser(JSON.parse(cachedUser));
      } catch {
        clearSession();
      }
    }
    setLoading(false);
  }, []);

  const clearSession = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
  };

  /** login({ email, password }) → stores token + user, returns user */
  const login = useCallback(async ({ email, password }) => {
    setError(null);
    const { data } = await authApi.login(email, password);
    // Backend returns: { token, employee_id, name, role, email, ... }
    const token = data.token || data.access_token;
    localStorage.setItem(TOKEN_KEY, token);

    // Fetch full user profile
    const { data: userData } = await authApi.me();
    localStorage.setItem(USER_KEY, JSON.stringify(userData));
    setUser(userData);
    return userData;
  }, []);

  /** logout → clear state + redirect handled by caller */
  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore errors — always clear locally
    } finally {
      clearSession();
    }
  }, []);

  const value = {
    user,
    role: user?.role?.toUpperCase() || null,
    isAuthenticated: !!user,
    loading,
    error,
    login,
    logout,
    setUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
