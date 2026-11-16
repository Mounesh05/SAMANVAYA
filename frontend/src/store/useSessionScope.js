import { useAuthStore } from './useAuthStore';

// Keep organization-dependent queries separate across accounts and tenants.
export function useSessionScope() {
  return useAuthStore((state) => JSON.stringify([state.user?.employee_id, state.user?.org_id]));
}
