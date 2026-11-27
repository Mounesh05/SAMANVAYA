import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { rolesApi } from '../../api/roles.api';
import { tasksApi } from '../../api/tasks.api';
import { sprintsApi } from '../../api/sprints.api';
import { projectsApi } from '../../api/projects.api';
import { employeesApi } from '../../api/employees.api';
import { useAuthStore } from '../../store/useAuthStore';
import { roleUser } from '../../tests/utils/roleUser';
import { PMDashboardPage } from './PMDashboardPage';
import { TasksPage } from '../tasks/TasksPage';

vi.mock('../../api/roles.api');
vi.mock('../../api/projects.api');
vi.mock('../../api/tasks.api');
vi.mock('../../api/employees.api');
vi.mock('../../api/sprints.api');

it('opens the exact task in the second project from an age-bucket drilldown', async () => {
  const projects = [{ id: 'P1', name: 'First project', status: 'active' }, { id: 'P2', name: 'Second project', status: 'active' }];
  const task = { id: 'T-7', title: 'Catalog search', project_id: 'P2', status: 'blocked', assignee_id: 'Dev' };
  useAuthStore.setState({ user: roleUser('PM', { employee_id: 'PM-1', org_id: 'ORG' }) });
  projectsApi.list.mockResolvedValue(projects);
  rolesApi.getPMDashboard.mockResolvedValue({ projects, summary: {} });
  rolesApi.getPMBlockedWork.mockResolvedValue({ counts: { week_plus: 1 }, tasks: [{
    task_id: task.id, title: task.title, project_id: task.project_id, project_name: 'Second project',
    age_days: 8, blocked_since: '2026-11-01T12:00:00Z', assignee_id: 'Dev',
  }], matched: 1, as_of: '2026-11-09T12:00:00Z' });
  tasksApi.listByProject.mockImplementation(async (id) => id === 'P2' ? [task] : []);
  tasksApi.getAvailableTransitions.mockResolvedValue({ allowed_statuses: [] });
  tasksApi.getDelivery.mockRejectedValue(new Error('No test evidence'));
  employeesApi.list.mockResolvedValue([]);
  sprintsApi.listByProject.mockResolvedValue([]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/pm/dashboard']}>
    <Routes><Route path="/pm/dashboard" element={<PMDashboardPage />} /><Route path="/tasks" element={<TasksPage />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
  const ageBar = await screen.findByRole('button', { name: '7 days or more: 1' });
  ageBar.focus();
  await userEvent.setup().keyboard(' ');
  expect(await screen.findByRole('heading', { name: '7 days or more' })).toBeVisible();
  const link = await screen.findByRole('link', { name: task.title });
  expect(link).toHaveAttribute('href', '/tasks?project=P2&task=T-7');
  fireEvent.click(link);
  const detail = await screen.findByRole('dialog', { name: task.title });
  expect(within(detail).getByText('Task ID: T-7')).toBeVisible();
  expect(tasksApi.getDelivery).toHaveBeenCalledWith('T-7');
  expect(tasksApi.listByProject).toHaveBeenCalledWith('P2');
  expect(tasksApi.listByProject).not.toHaveBeenCalledWith('P1');
  fireEvent.click(within(detail).getByText('Close', { selector: 'button' }));
  expect(screen.queryByRole('dialog')).toBeNull();
});

it('shows an unavailable deep link without fetching tasks from a removed project', async () => {
  vi.clearAllMocks();
  useAuthStore.setState({ user: roleUser('PM', { employee_id: 'PM-1', org_id: 'ORG' }) });
  projectsApi.list.mockResolvedValue([{ id: 'P1', name: 'Managed project' }]);
  employeesApi.list.mockResolvedValue([]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/tasks?project=P2&task=T-7']}>
    <TasksPage />
  </MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText('This task is unavailable in the selected project.')).toBeVisible();
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(tasksApi.listByProject).not.toHaveBeenCalled();
  expect(tasksApi.getDelivery).not.toHaveBeenCalled();
});
