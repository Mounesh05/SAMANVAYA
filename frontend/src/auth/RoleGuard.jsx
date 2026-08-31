import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';

export function RoleGuard({ allowedRoles = [], children }) {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase();
  const isAdmin = user?.is_admin || false;

  if (!role) {
    return <Navigate to="/login" replace />;
  }

  // Admin has access to all roles, otherwise check allowed roles list
  if (isAdmin || allowedRoles.length === 0 || allowedRoles.includes(role)) {
    return children;
  }

  // Redirect to user's appropriate role dashboard
  const defaultDashboard = `/${role.toLowerCase()}/dashboard`;
  return <Navigate to={defaultDashboard} replace />;
}
