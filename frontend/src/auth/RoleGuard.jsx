import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { canOpenPage } from '../routes/access';
import { homePath } from '../routes/home';

/**
 * Guards a route using the shared page-access table (routes/access.js), which
 * decides by permission (or, for role dashboards, by persona). Every route
 * passes `page`; without one the route is open to any signed-in user.
 */
export function RoleGuard({ page, children }) {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase();

  if (!role) {
    return <Navigate to="/login" replace />;
  }

  if (!page || canOpenPage(user, page)) {
    return children;
  }

  // Send the user to their own dashboard ("/" shows "not found" for an unknown role).
  return <Navigate to={homePath(user) || '/'} replace />;
}
