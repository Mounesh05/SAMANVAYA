import { useAuthStore } from '../store/useAuthStore';
import { hasPermission } from './permissions';

export function PermissionGuard({ permission, fallback = null, children }) {
  const { user } = useAuthStore();
  return hasPermission(user, permission) ? children : fallback;
}
