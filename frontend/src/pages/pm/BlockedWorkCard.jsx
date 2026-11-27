import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { rolesApi } from '../../api/roles.api';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { BarList } from '../../components/charts/Charts';
import { Table } from '../../components/common/Table';

const labels = {
  under_day: 'Under 1 day', one_two_days: '1–2 days', three_six_days: '3–6 days',
  week_plus: '7 days or more', unknown: 'Age unknown',
};
const pageSize = 12;
const columns = [
  { key: 'title', header: 'Task', render: (item) => <Link to={{
    pathname: '/tasks', search: new URLSearchParams({ project: item.project_id, task: item.task_id }).toString(),
  }}>{item.title}</Link> },
  { key: 'project_name', header: 'Project' },
  { key: 'assignee_id', header: 'Owner', render: (row) => row.assignee_id || 'Unassigned' },
  { key: 'age_days', header: 'Blocked for', render: (row) => {
    if (row.age_days == null) return 'Age unknown';
    const age = row.age_days === 0 ? 'Under 1 day' : `${row.age_days} ${row.age_days === 1 ? 'day' : 'days'}`;
    return <time dateTime={row.blocked_since} title={row.blocked_since}>{age}</time>;
  } },
];

export function BlockedWorkCard({ sessionScope }) {
  const [group, setGroup] = useState('all');
  const [offset, setOffset] = useState(0);
  const result = useQuery({
    queryKey: ['pm-blocked-work', sessionScope, group, offset],
    queryFn: () => rolesApi.getPMBlockedWork(group, offset, pageSize),
  });
  function chooseGroup(key) {
    setGroup(key);
    setOffset(0);
  }
  const data = result.data;
  const asOf = data?.as_of && new Date(data.as_of);
  return <Card title="Blocked work by age" subtitle="Active projects you manage">
    {result.isError ? <div role="alert">
      <p>Blocked work could not be loaded.</p><Button size="sm" onClick={() => result.refetch()}>Retry</Button>
    </div> : !data ? <p role="status">Loading blocked tasks…</p> : <>
      {asOf && <p className="dash-sub">As of <time dateTime={data.as_of}>{asOf.toLocaleString()}</time></p>}
      <BarList label="Blocked tasks" emptyText="No blocked tasks in your active projects."
        items={Object.entries(labels).map(([key, label]) => ({ key, label, value: data.counts[key] }))}
        onSelect={(item) => chooseGroup(item.key)} />
      {(data.matched > 0 || group !== 'all' || offset > 0) && <>
        <h4 className="dash-sub">{group === 'all' ? 'All blocked tasks' : labels[group]}</h4>
        {group !== 'all' && <Button variant="ghost" size="sm" onClick={() => chooseGroup('all')}>Show all ages</Button>}
        <Table columns={columns} data={data.tasks} keyExtractor={(item) => item.task_id}
          emptyMessage="No blocked tasks on this page." />
        {(data.matched > pageSize || offset > 0) && <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
          <Button size="sm" variant="ghost" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - pageSize))}>Previous</Button>
          <span>{data.tasks.length ? `${offset + 1}–${offset + data.tasks.length} of ${data.matched}` : `0 of ${data.matched}`}</span>
          <Button size="sm" variant="ghost" disabled={offset + pageSize >= data.matched} onClick={() => setOffset(offset + pageSize)}>Next</Button>
        </div>}
      </>}
    </>}
  </Card>;
}
