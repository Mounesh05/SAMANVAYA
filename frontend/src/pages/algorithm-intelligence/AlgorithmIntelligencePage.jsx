import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Select } from '../../components/common/Select';
import { projectsApi } from '../../api/projects.api';
import { algorithmsApi } from '../../api/algorithms.api';
import { useSessionScope } from '../../store/useSessionScope';
import { useAuthStore } from '../../store/useAuthStore';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';
import { AlgorithmComparisonPanel, RunDetails } from '../code-quality/AlgorithmComparisonPanel';
import { PRAlgorithmIntelligencePanel } from '../code-quality/PRAlgorithmIntelligencePanel';
import { RequirementReviewWorkspace } from './RequirementReviewWorkspace';
import '../code-quality/CodeQuality.css';
import './AlgorithmIntelligence.css';

import { RepositoryAnalysis } from './RepositoryAnalysis';

const sections = ['Analyses', 'Experiments', 'Requirements', 'History'];

function BenchmarkHistory({ projectId }) {
  const scope = useSessionScope();
  const user = useAuthStore(state => state.user);
  const [selected, setSelected] = useState('');
  const history = useQuery({
    queryKey: ['algorithms', 'history', projectId, scope],
    queryFn: () => algorithmsApi.getHistory(projectId, 30),
    retry: false,
  });
  const run = useQuery({
    queryKey: ['algorithms', 'run', selected, scope],
    queryFn: () => algorithmsApi.getRun(selected),
    enabled: Boolean(selected) && !history.isError,
    retry: false,
  });
  return <Card title="Benchmark history" className="ai-stack">
    {history.isPending && <p role="status">Loading history…</p>}
    {history.isError && <p role="alert">{history.error.message} <Button size="sm" variant="outline" onClick={() => history.refetch()}>Retry</Button></p>}
    {!history.isError && (history.data?.history || []).length === 0 && history.isSuccess && <p>No saved benchmark runs.</p>}
    {!history.isError && (history.data?.history || []).map(item => <div key={item.run_id} className="ai-list-row">
      <div><strong>{item.run_id}</strong><p>{item.status}{item.created_at ? ' · ' + item.created_at : ''}</p></div>
      <Button variant="outline" size="sm" onClick={() => setSelected(item.run_id)}>View run</Button>
    </div>)}
    {selected && !history.isError && run.isPending && <p role="status">Loading run…</p>}
    {run.isError && <p role="alert">{run.error.message}</p>}
    {selected && !history.isError && !run.isError && run.data?.project_id === projectId &&
      <details className="ai-disclosure"><summary>Run details · {selected}</summary>
        <RunDetails key={run.data.run_id} run={run.data} canSubmit={hasPermission(user, PERMISSIONS.USE_ENGINEERING_INTELLIGENCE)} onSelectRun={setSelected} />
      </details>}
    {selected && !history.isError && !run.isError && run.isSuccess && run.data?.project_id !== projectId &&
      <p role="alert">This run could not be bound to the selected project.</p>}
  </Card>;
}

function Workspace({ scope }) {
  const [section, setSection] = useState(() => sections.find(s => s === new URLSearchParams(window.location.search).get('section')) || 'Analyses');
  const [selection, setSelection] = useState(() => new URLSearchParams(window.location.search).get('project') || '');
  const projects = useQuery({ queryKey: ['algorithm-projects', scope], queryFn: () => projectsApi.list(), retry: false });
  const options = projects.isSuccess ? (projects.data || []).filter(p => p.id).map(p => ({ value: p.id, label: p.name || p.id })) : [];
  const projectId = options.some(p => p.value === selection) ? selection : '';
  const needsProject = section !== 'Analyses';
  return <div className="ai-workspace">
    <PageHeader title="Algorithm Intelligence" subtitle="Analyze functions, validate behavior and measure performance." />
    <nav className="ai-section-nav" aria-label="Algorithm workspace">
      {sections.map(name => <Button key={name} variant={section === name ? 'primary' : 'ghost'} aria-pressed={section === name} onClick={() => setSection(name)}>{name}</Button>)}
    </nav>
    <div className="ai-project-filter">
      <Select label="Project" placeholder={needsProject ? 'Select a project' : 'All accessible projects'} value={projectId}
        options={options} disabled={!projects.isSuccess} onChange={event => setSelection(event.target.value)} />
      {projects.isPending && <p role="status">Loading projects…</p>}
      {projects.isError && <p role="alert">{projects.error.message} <Button variant="outline" size="sm" onClick={() => projects.refetch()}>Retry</Button></p>}
    </div>
    {section === 'Analyses' && projectId && <RepositoryAnalysis key={projectId} projectId={projectId} />}
    {section === 'Analyses' && !projects.isError && <PRAlgorithmIntelligencePanel key={projectId || 'all'} projectId={projectId} onReview={id => {setSelection(id); setSection('Requirements');}} compact />}
    {needsProject && !projectId && <Card><p>Select a project to continue.</p></Card>}
    {section === 'Experiments' && projectId && <AlgorithmComparisonPanel key={projectId} workspaceProject={projectId} />}
    {section === 'Requirements' && projectId && <RequirementReviewWorkspace key={projectId} projectId={projectId} />}
    {section === 'History' && projectId && <BenchmarkHistory key={projectId} projectId={projectId} />}
  </div>;
}

export function AlgorithmIntelligencePage() {
  const scope = useSessionScope();
  return <Workspace key={scope} scope={scope} />;
}
