import { useAuth } from './AuthContext';
import { ROLE_PERMISSIONS } from './permissions';

/**
 * PermissionGuard — conditionally renders children based on permission.
 * If user doesn't have the permission, renders `fallback` (or nothing).
 */
export function PermissionGuard({ permission, children, fallback = null }) {
  const { role } = useAuth();
  const userPermissions = ROLE_PERMISSIONS[role] || [];

  if (!userPermissions.includes(permission)) {
    return fallback;
  }

  return children;
}

/**
 * usePermission(permission) → boolean
 * Useful for conditional rendering in JSX without a wrapper component.
 */
export function usePermission(permission) {
  const { role } = useAuth();
  const userPermissions = ROLE_PERMISSIONS[role] || [];
  return userPermissions.includes(permission);
}
