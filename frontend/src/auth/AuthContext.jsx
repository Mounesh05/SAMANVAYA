import React, { createContext, useEffect } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { authApi } from '../api/auth.api';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const { token, user, isAuthenticated, setAuth, setUser, logout } = useAuthStore();

  useEffect(() => {
    // Refresh the profile from the backend on every session start: it carries
    // the current role and permission list, so a saved copy can never grant
    // stale access in the UI.
    if (!token) return;
    let cancelled = false;
    authApi
      .getMe()
      .then((userData) => {
        if (!cancelled) setUser(userData);
      })
      .catch(() => {
        if (!cancelled && !useAuthStore.getState().user) logout();
      });
    return () => {
      cancelled = true;
    };
  }, [token, setUser, logout]);

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isAuthenticated,
        role: user?.role?.toUpperCase(),
        isAdmin: user?.is_admin || false,
        setAuth,
        setUser,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
