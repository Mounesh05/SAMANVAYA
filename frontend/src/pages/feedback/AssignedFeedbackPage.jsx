import React from 'react';
import { PageHeader } from '../../components/layout/PageHeader';
import { AssignedObservations } from '../../components/performance/AssignedObservations';
import { useAuthStore } from '../../store/useAuthStore';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';

export function AssignedFeedbackPage() {
  const user = useAuthStore((s) => s.user);
  return <div className="scoring-stack">
    <PageHeader title="Assigned feedback" subtitle="Record period-specific observations without inventing a numerical rating." />
    {hasPermission(user, PERMISSIONS.SUBMIT_HR_FEEDBACK) && <p className="scoring-help">HR assignments cover workplace observations only. Technical performance is not rescored here.</p>}
    <AssignedObservations key={user?.employee_id} />
  </div>;
}
