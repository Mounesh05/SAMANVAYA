import React from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { hasPermission } from './permissions';

export function PermissionGuard({ permission, fallback = null, children }) {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase();
  const isAdmin = user?.is_admin || false;

  if (hasPermission(role, permission, isAdmin)) {
    return children;
  }

  return fallback;
}
