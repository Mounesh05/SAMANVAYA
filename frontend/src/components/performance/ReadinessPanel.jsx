import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { performanceApi } from '../../api/performance.api';
import { useAuthStore } from '../../store/useAuthStore';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { requestError } from '../../utils/performanceScoring';
import './scoring.css';

export function ReadinessPanel() {
  const user = useAuthStore((s) => s.user);
  const query = useQuery({ queryKey: ['scoring-readiness', user?.employee_id, user?.role],
    queryFn: () => performanceApi.getReadiness(), enabled: Boolean(user), retry: false });
  return <Card title="Scoring readiness" className="scoring-stack">
    {query.isPending ? <p role="status">Checking scoring readiness…</p> : query.isError ?
      <div role="alert"><p>{requestError(query.error)}</p><Button variant="secondary" onClick={() => query.refetch()}>Retry readiness</Button></div> : <>
        <p className="scoring-status">Calibration and release approval required</p>
        <p className="scoring-help">No production numerical evaluation is enabled. Historical values remain readable; missing evidence is not a low score.</p>
        <ul>{query.data?.roles?.map((item) => <li key={item.role}>{item.role}: {item.status.replaceAll('_', ' ').toLowerCase()}</li>)}</ul>
        <details><summary>What is still needed</summary><ul>{query.data?.unresolved_decisions?.map((item) => <li key={item}>{item}</li>)}</ul></details>
      </>}
  </Card>;
}
