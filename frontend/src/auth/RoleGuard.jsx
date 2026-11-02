import { Navigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

/**
 * RoleGuard — allows access only if user's role is in `allowedRoles`.
 * Shows a 403 page if the role doesn't match.
 */
export function RoleGuard({ allowedRoles = [], children, fallback }) {
  const { role } = useAuth();

  if (!role || !allowedRoles.includes(role)) {
    if (fallback) return fallback;
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
}
