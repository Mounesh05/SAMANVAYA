import { useQuery } from '@tanstack/react-query';
import { notificationsApi } from '../api/notifications.api';
import { useAuthStore } from '../store/useAuthStore';

export function useNotifications() {
  const { isAuthenticated } = useAuthStore();

  const { data, refetch, isLoading } = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: () => notificationsApi.getUnreadCount(),
    enabled: isAuthenticated,
    refetchInterval: 30000, // 30s polling as specified
    refetchOnWindowFocus: true,
  });

  return {
    unreadCount: data?.unread || 0,
    refetch,
    isLoading,
  };
}
