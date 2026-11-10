import React from 'react';
import { Table } from '../common/Table';

export function AutomatedTestRunsTable({ runs = [], isLoading = false }) {
  const columns = [
    { key: 'run_id', header: 'Run ID', render: (r) => <span>{r.run_id || r.id}</span> },
    { key: 'branch', header: 'Branch', render: (r) => <strong>{r.branch || 'main'}</strong> },
    { key: 'status', header: 'Status', render: (r) => <span>{r.status}</span> },
    { key: 'created_at', header: 'Date', render: (r) => <span>{r.created_at || 'Recent'}</span> },
  ];

  if (isLoading) {
    return <div style={{ padding: '1rem', color: 'var(--text-muted)' }}>Loading automated test runs...</div>;
  }

  return <Table columns={columns} data={runs} emptyMessage="No automated test runs found." />;
}

