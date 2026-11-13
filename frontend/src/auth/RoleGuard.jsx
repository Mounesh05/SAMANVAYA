import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { canOpenPage } from '../routes/access';

/**
 * Guards a route using the shared page-access table (routes/access.js).
 * `allowedRoles` is kept only for callers outside the main router.
 */
export function RoleGuard({ page, allowedRoles = [], children }) {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase();

  if (!role) {
    return <Navigate to="/login" replace />;
  }

  const allowed = page
    ? canOpenPage(user, page)
    : allowedRoles.length === 0 || allowedRoles.includes(role);  // CR-008: no admin bypass
  if (allowed) {
    return children;
  }

  // Redirect to user's appropriate role dashboard
  return <Navigate to={`/${role.toLowerCase()}/dashboard`} replace />;
}
