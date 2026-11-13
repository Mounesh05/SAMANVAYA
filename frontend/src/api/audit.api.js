import apiClient from './client';

/** Audit trail (VIEW_AUDIT_LOGS). HR accounts receive HR-relevant events only. */
export const auditApi = {
  list: async ({ action, actorId, resourceType, resourceId, startDate, endDate, limit = 200 } = {}) =>
    apiClient.get('/audit/logs', {
      params: {
        action: action || undefined,
        actor_id: actorId || undefined,
        resource_type: resourceType || undefined,
        resource_id: resourceId || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        limit,
      },
    }),
};
