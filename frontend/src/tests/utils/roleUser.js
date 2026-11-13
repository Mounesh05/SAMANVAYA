import rolePermissions from '../fixtures/rolePermissions.json';

/** Permissions /api/auth/me returns for `role` (no HR designation). Admins
 * also get the backend's ADMIN_PERMISSIONS. The fixture is checked against the
 * backend by backend/tests/test_frontend_permission_parity.py. */
export function permissionsFor(role, isAdmin = false) {
  const base = rolePermissions[String(role || '').toUpperCase()] || [];
  return isAdmin ? [...new Set([...base, ...rolePermissions._ADMIN])].sort() : base;
}

/** A user as /api/auth/me returns it for `role`. */
export function roleUser(role, overrides = {}) {
  const normalized = String(role || '').toUpperCase();
  const isAdmin = Boolean(overrides.is_admin);
  return {
    employee_id: `DEMO-${normalized}`,
    name: `User ${normalized}`,
    role,
    is_admin: isAdmin,
    permissions: permissionsFor(role, isAdmin),
    ...overrides,
  };
}

/** Adds the role's real permissions to a hand-built test user (unless it sets its own). */
export function withPermissions(user) {
  if (!user || Array.isArray(user.permissions)) return user;
  return { ...user, permissions: permissionsFor(user.role, Boolean(user.is_admin)) };
}
