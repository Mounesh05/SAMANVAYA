import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { ROLES } from '../utils/constants';
import { NotFoundPage } from '../pages/error/NotFoundPage';

/**
 * Where a signed-in person lands, and which "return to" paths are safe after
 * sign-in. The router ("/" and "/dashboard"), RoleGuard and the login page all
 * use these, so the rules live in one place.
 */

const KNOWN_ROLES = new Set(Object.values(ROLES));
const PUBLIC_PATHS = new Set(['/login', '/setup']);
// "/dashboard" has no page of its own: it means "my home page".
const HOME_ALIASES = new Set(['/dashboard']);
// Backslashes (browsers read "/\host" as "//host") and control characters.
const UNSAFE_CHARACTERS = /[\\\u0000-\u001f\u007f]/;

/** The person's own dashboard, or null when the role is not one of the 7 roles. */
export function homePath(user) {
  const role = String(user?.role || '').toUpperCase();
  return KNOWN_ROLES.has(role) ? `/${role.toLowerCase()}/dashboard` : null;
}

/**
 * The page to open after sign-in. Only same-app paths are kept; anything else
 * (other hosts, protocol-relative or backslash paths, "..", the sign-in pages
 * themselves, "/dashboard") goes to "/", which sends the person home by role.
 * Access to the kept path is still decided by RoleGuard when it renders.
 */
export function safeReturnPath(from) {
  const path = from?.pathname;
  const search = from?.search || '';
  if (typeof path !== 'string' || typeof search !== 'string') return '/';
  if (!path.startsWith('/') || path.startsWith('//') || UNSAFE_CHARACTERS.test(path + search)) return '/';
  if (search && !search.startsWith('?')) return '/';
  let decoded;
  try {
    decoded = decodeURIComponent(path);
  } catch {
    return '/';
  }
  if (decoded.startsWith('//') || UNSAFE_CHARACTERS.test(decoded) || decoded.split('/').includes('..')) return '/';
  const normal = path.replace(/\/+$/, '') || '/';
  if (PUBLIC_PATHS.has(normal) || HOME_ALIASES.has(normal)) return '/';
  return path + search;
}

/** "/" and "/dashboard": send the person to their own role dashboard. */
export function HomeRedirect() {
  const { user, isAuthenticated } = useAuthStore();
  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }
  const home = homePath(user);
  // An unrecognised role has no dashboard; show "not found" rather than
  // guessing a role (which would only bounce off RoleGuard).
  return home ? <Navigate to={home} replace /> : <NotFoundPage />;
}
