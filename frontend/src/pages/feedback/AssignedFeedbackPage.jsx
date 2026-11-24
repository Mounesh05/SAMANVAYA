import React from 'react';
import { PageHeader } from '../../components/layout/PageHeader';
import { AssignedObservations } from '../../components/performance/AssignedObservations';
import { useAuthStore } from '../../store/useAuthStore';
import { useSessionScope } from '../../store/useSessionScope';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';

export function AssignedFeedbackPage() {
  const user = useAuthStore((s) => s.user);
  const sessionScope = useSessionScope();
  return <div className="scoring-stack">
    <PageHeader title="Assigned feedback" subtitle="Review observations for your assigned employees and assessment periods." />
    {hasPermission(user, PERMISSIONS.SUBMIT_HR_FEEDBACK) && <p className="scoring-help">HR assignments cover workplace observations only.</p>}
    {user?.role === 'CEO' ? <p>No active assigned reviews. Executive access includes assessment history.</p> :
      <AssignedObservations key={sessionScope} />}
  </div>;
}
