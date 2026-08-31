import React, { createContext, useEffect } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { authApi } from '../api/auth.api';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const { token, user, isAuthenticated, setAuth, setUser, logout } = useAuthStore();

  useEffect(() => {
    // If token exists but user profile is missing, fetch current user
    if (token && !user) {
      authApi
        .getMe()
        .then((userData) => setUser(userData))
        .catch(() => logout());
    }
  }, [token, user, setUser, logout]);

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
