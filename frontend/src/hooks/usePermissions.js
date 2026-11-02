import { useAuth } from '../auth/AuthContext';
import { ROLE_PERMISSIONS, ROLE_NAV, getRoleDashboardPath } from '../auth/permissions';

/**
 * usePermissions() → { can(permission), navItems, dashboardPath }
 */
export function usePermissions() {
  const { role } = useAuth();
  const userPermissions = ROLE_PERMISSIONS[role] || [];

  return {
    can: (permission) => userPermissions.includes(permission),
    permissions: userPermissions,
    navItems: ROLE_NAV[role] || [],
    dashboardPath: getRoleDashboardPath(role),
  };
}
