import React from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { rolesApi } from '../../api/roles.api';
import { useSessionScope } from '../../store/useSessionScope';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { PageHeader } from '../../components/layout/PageHeader';

const number = (value) => Number.isSafeInteger(value) && value > 0;
const safeRepository = (repo) => typeof repo === 'string' && /^[\w.-]+\/[\w.-]+$/.test(repo)
  && repo.split('/').every((segment) => !['.', '..'].includes(segment));

export function AttemptLink({ run }) {
  const name = run.name || 'Workflow';
  const title = `${name} #${run.id} · attempt ${run.attempt}`;
  return safeRepository(run.repository) && number(run.id) && number(run.attempt)
    ? <a href={`https://github.com/${run.repository}/actions/runs/${run.id}/attempts/${run.attempt}`} target="_blank" rel="noreferrer">{title}</a>
    : title;
}

export function DeploymentLink({ row, children }) {
  if (!safeRepository(row.repository) || !number(row.id)) return children;
  const params = new URLSearchParams({ repository: row.repository, deployment_id: String(row.id) });
  return <Link to={`/deployments?${params}`}>{children}</Link>;
}

function utcTimestamp(value) {
  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? new Date(timestamp).toISOString().replace('T', ' ').slice(0, 19) : '—';
}

function Result({ state }) {
  const tone = { success: 'success', failure: 'danger', error: 'danger', timed_out: 'danger', in_progress: 'info' };
  return <Badge size="sm" variant={tone[state] || 'default'}>{String(state || 'unconfirmed').replaceAll('_', ' ')}</Badge>;
}

export function OperationsHistory({ kind }) {
  const workflows = kind === 'pipelines';
  const title = workflows ? 'Workflow attempts' : 'Deployments';
  const scope = useSessionScope();
  const [search, setSearch] = useSearchParams();
  const { owner, repo } = useParams();
  const repository = search.get('repository') || (owner && repo ? `${owner}/${repo}` : undefined);
  const candidate = Number(search.get('page'));
  const page = number(candidate) ? candidate : 1;
  const params = workflows
    ? { page, day: search.get('day') || undefined, outcome: search.get('outcome') || undefined }
    : { page, repository, today: search.get('today') === 'true', deployment_id: search.get('deployment_id') || undefined };
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: [kind, scope, params],
    queryFn: () => workflows ? rolesApi.getPipelines(params) : rolesApi.getDeployments(params),
  });
  if (isLoading) return <LoadingState message={`Loading ${title.toLowerCase()}…`} />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;
  const rows = data?.[kind] || [];
  const filter = workflows ? [params.day, params.outcome] : [params.today && 'Today', repository, params.deployment_id];
  const subtitle = [params.deployment_id ? 'Deployment record' : 'Last 14 UTC dates', ...filter].filter(Boolean).join(' · ');
  const columns = [
    workflows
      ? { key: 'name', header: 'Workflow', render: (row) => <AttemptLink run={row} /> }
      : { key: 'id', header: 'Deployment', render: (row) => params.deployment_id ? `#${row.id}` : <DeploymentLink row={row}>#{row.id}</DeploymentLink> },
    { key: 'repository', header: 'Repository' },
    workflows ? { key: 'branch', header: 'Branch' } : { key: 'environment', header: 'Environment' },
    { key: 'sha', header: 'Commit', render: (row) => safeRepository(row.repository) && /^[a-f0-9]{40}$/i.test(row.sha)
      ? <a href={`https://github.com/${row.repository}/commit/${row.sha}`} target="_blank" rel="noreferrer"><code>{row.sha.slice(0, 12)}</code></a>
      : '—' },
    { key: 'status', header: 'Status', render: (row) => <Result state={row.conclusion || row.status} /> },
    { key: 'updated_at', header: 'Updated (UTC)', render: (row) => utcTimestamp(row.updated_at) },
  ];
  if (!workflows) columns.splice(3, 0, { key: 'deployed_by', header: 'Requested by' });
  const go = (next) => {
    const query = new URLSearchParams(search);
    query.set('page', String(next));
    setSearch(query);
  };
  return <div className="dash">
    <PageHeader title={title} subtitle={subtitle} />
    <Card title={`${data?.total ?? 0} ${title.toLowerCase()}`} action={filter.some(Boolean) ? <Link to={`/${kind}`}>Clear filters</Link> : null}>
      <Table columns={columns} data={rows} keyExtractor={(row) => `${row.repository}/${row.id}/${row.attempt || ''}`}
        emptyMessage="No matching GitHub records in your projects." />
      {(page > 1 || data.total > page * data.page_size) && <nav aria-label="History pages">
        <Button size="sm" variant="ghost" disabled={page === 1} onClick={() => go(page - 1)}>Previous</Button>
        <span>Page {page}</span>
        <Button size="sm" variant="ghost" disabled={page * data.page_size >= data.total} onClick={() => go(page + 1)}>Next</Button>
      </nav>}
    </Card>
  </div>;
}
