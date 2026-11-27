import React from 'react';
import { useMutation } from '@tanstack/react-query';
import { algorithmsApi } from '../../api/algorithms.api';
import { Button } from '../../components/common/Button';
import { useAuthStore } from '../../store/useAuthStore';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';

export function AlgorithmAdvisory({ run, kind, refresh }) {
  const user = useAuthStore(state => state.user);
  const allowed = hasPermission(user, PERMISSIONS.USE_ENGINEERING_INTELLIGENCE);
  const retry = useMutation({
    mutationFn: () => kind === 'pr' ? algorithmsApi.retryPRAdvisory(run.run_id) : algorithmsApi.retryBenchmarkAdvisory(run.run_id),
    onSuccess: () => refresh?.(),
  });
  const report = retry.data || run.algorithm_advisory;
  const status = report?.status || 'not yet available';
  const expired = status === 'running' && Date.parse(report.lease_expires_at || '') <= Date.now();
  const terminal = ['completed', 'failed', 'insufficient_evidence', 'unsupported', 'unavailable'].includes(run.status);
  return <section className="ai-stack" aria-label="Algorithm AI advisory">
    <h4>AI advisory</h4>
    <p>Report: {run.report_status || 'historical'} · AI: {expired ? 'interrupted' : status.replaceAll('_', ' ')}</p>
    {report?.status === 'completed' && report.advisory && <div className="ai-stack">
      <p>{report.advisory.summary}</p>
      {(report.advisory.suggestions || []).map((s, i) => <div className="ai-review" key={i}>
        <strong>{s.type.replaceAll('_',' ').toLowerCase()}</strong><p>{s.why}</p><p>{s.action}</p>
        <details><summary>Evidence references</summary><p>{s.evidence_refs.join(' · ')}</p></details>
      </div>)}
      {report.advisory.limitations?.length > 0 && <details><summary>Limitations</summary><ul>{report.advisory.limitations.map((s,i)=><li key={i}>{s}</li>)}</ul></details>}
      <small>Advisory hypotheses only. Deterministic results are authoritative.</small>
    </div>}
    {report?.error && <p role="status">{report.error}</p>}
    {retry.isError && <p role="alert">{retry.error.message}</p>}
    {allowed && terminal && !run.historical_only && status !== 'completed' && (status !== 'running' || expired) &&
      (report?.attempt || 0) < 3 && <Button size="sm" variant="outline" isLoading={retry.isPending} onClick={() => retry.mutate()}>Retry AI only</Button>}
  </section>;
}
