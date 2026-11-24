/**
 * Role dashboards: charts beside the key figures, built only from what the
 * API returns. Chart pieces first, then each dashboard with mocked data.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { BarList, Meter, SegmentedBar, StackedColumns, Timeline } from '../components/charts/Charts';
import { dailyPoints, trendPoints } from '../components/charts/chartData';
import { CEODashboardPage } from '../pages/ceo/CEODashboardPage';
import { PMDashboardPage } from '../pages/pm/PMDashboardPage';
import { LeadDashboardPage } from '../pages/lead/LeadDashboardPage';
import { DeveloperDashboardPage } from '../pages/developer/DeveloperDashboardPage';
import { QADashboardPage } from '../pages/qa/QADashboardPage';
import { DevOpsDashboardPage } from '../pages/devops/DevOpsDashboardPage';
import { HRDashboardPage } from '../pages/hr/HRDashboardPage';
import { rolesApi } from '../api/roles.api';
import { performanceApi } from '../api/performance.api';
import { qaApi } from '../api/qa.api';
import { transfersApi } from '../api/transfers.api';
import { useAuthStore } from '../store/useAuthStore';
import { roleUser } from './utils/roleUser';

vi.mock('../api/roles.api', () => ({
  rolesApi: {
    getCEODashboard: vi.fn(), getExecutionHealth: vi.fn(), getPMDashboard: vi.fn(), getPMBlockedWork: vi.fn(), getLeadDashboard: vi.fn(),
    getDeveloperDashboard: vi.fn(), getDevOpsDashboard: vi.fn(), getHRDashboard: vi.fn(),
  },
}));
vi.mock('../api/performance.api', () => ({ performanceApi: { getDeveloperDashboard: vi.fn() } }));
vi.mock('../api/transfers.api', () => ({ transfersApi: { getTransfers: vi.fn() } }));
vi.mock('../api/qa.api', () => ({
  qaApi: {
    getProjects: vi.fn(), getDashboard: vi.fn(), getCIConfigs: vi.fn(), getTestRuns: vi.fn(),
    enableCIIntegration: vi.fn(), disableCIIntegration: vi.fn(),
  },
}));

function renderPage(ui) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe('chart pieces', () => {
  it('splits a whole into parts, prints shares and counts, and names every part', () => {
    render(<SegmentedBar label="Tasks" parts={[
      { label: 'Done', value: 3, tone: 'good' },
      { label: 'Blocked', value: 1, tone: 'critical' },
      { label: 'Other', value: 0, tone: 'neutral' },
    ]} />);
    expect(screen.getByRole('img', { name: 'Tasks: Done 3 (75%), Blocked 1 (25%), Other 0 (0%)' })).toBeInTheDocument();
    expect(screen.getByText('75%')).toBeInTheDocument();
    expect(screen.queryByLabelText(/^Other:/)).not.toBeInTheDocument(); // a zero part draws nothing
    expect(screen.getAllByRole('listitem')).toHaveLength(3); // …but stays in the legend
  });

  it('shows a tooltip on hover and on keyboard focus', () => {
    render(<SegmentedBar label="Tasks" parts={[{ label: 'Done', value: 2, tone: 'good' }, { label: 'Blocked', value: 2, tone: 'critical' }]} />);
    fireEvent.focus(screen.getByLabelText('Done: 2 (50%)'));
    expect(screen.getByText('Share')).toBeInTheDocument();
    fireEvent.blur(screen.getByLabelText('Done: 2 (50%)'));
    expect(screen.queryByText('Share')).not.toBeInTheDocument();
  });

  it('says so when there is nothing to chart', () => {
    render(<SegmentedBar label="Tasks" emptyText="No tasks yet." parts={[{ label: 'Done', value: 0 }]} />);
    expect(screen.getByText('No tasks yet.')).toBeInTheDocument();
  });

  it('sorts bars, prints each value and folds the long tail into Other', () => {
    const items = Array.from({ length: 10 }, (_, i) => ({ key: `p${i}`, label: `Project ${i}`, value: i + 1 }));
    render(<BarList label="Risks" items={items} limit={3} />);
    const rows = screen.getAllByRole('listitem');
    expect(rows).toHaveLength(4);
    expect(within(rows[0]).getByText('Project 9')).toBeInTheDocument();
    expect(within(rows[3]).getByText('Other (7)')).toBeInTheDocument();
    expect(within(rows[3]).getByText('28')).toBeInTheDocument();
  });

  it('lets a bar open its item', () => {
    const onSelect = vi.fn();
    render(<BarList label="Risks" items={[{ key: 'P1', label: 'Atlas', value: 2 }]} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('button', { name: 'Atlas: 2' }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ key: 'P1' }));
  });

  it('labels a meter by state, not colour alone', () => {
    const { rerender } = render(<Meter label="Pass rate" value={92} thresholds={[70, 90]} />);
    expect(screen.getByRole('meter', { name: 'Pass rate' })).toHaveAttribute('aria-valuenow', '92');
    expect(screen.getByText('On track')).toBeInTheDocument();
    rerender(<Meter label="Pass rate" value={40} thresholds={[70, 90]} />);
    expect(screen.getByText('At risk')).toBeInTheDocument();
    rerender(<Meter label="Pass rate" value={null} emptyText="Nothing yet." />);
    expect(screen.getByText('Nothing yet.')).toBeInTheDocument();
  });

  it('counts dated records into days and keeps a table of the values', () => {
    const today = new Date(2026, 10, 14, 12);
    const records = [
      { at: '2026-11-14T09:00:00', ok: true },
      { at: '2026-11-14T10:00:00', ok: false },
      { at: '2026-11-13T10:00:00', ok: true },
      { at: '2026-10-01T10:00:00', ok: true }, // outside the window
      { at: null, ok: true },
    ];
    const points = dailyPoints(records, { days: 3, today, dateOf: (r) => r.at, bucketOf: (r) => (r.ok ? 'success' : 'failed') });
    expect(points.map((p) => p.key)).toEqual(['2026-11-12', '2026-11-13', '2026-11-14']);
    expect(points[2].values).toEqual({ success: 1, failed: 1 });

    const series = [{ key: 'success', label: 'Succeeded', tone: 'good' }, { key: 'failed', label: 'Failed', tone: 'critical' }];
    render(<StackedColumns label="Runs per day" data={points} series={series} />);
    const table = screen.getByRole('table');
    expect(within(table).getAllByRole('row')).toHaveLength(4);
    const trend = trendPoints([{ date: '2026-11-03', passed: 1 }, { date: '2026-11-01', passed: 2 }], ['passed', 'failed']);
    expect(trend.map((p) => p.key)).toEqual(['2026-11-01', '2026-11-02', '2026-11-03']); // gaps filled, in date order
    expect(trend[0].values).toEqual({ passed: 2, failed: 0 });
    expect(trend[1].values).toEqual({ passed: 0, failed: 0 });
  });

  it('flags open projects that are past their target end', () => {
    render(<Timeline label="Schedule" today={new Date(2026, 10, 14)} items={[
      { key: 'a', label: 'Atlas', start: '2026-09-01', end: '2026-10-31', open: true },
      { key: 'b', label: 'Beacon', start: '2026-10-01', end: '2026-12-31', open: true },
      { key: 'c', label: 'Comet', start: '2026-08-01', end: '2026-09-30', open: false },
      { key: 'd', label: 'No dates', open: true },
    ]} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
    expect(screen.getByLabelText(/^Atlas: .*past target end$/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Beacon: /).getAttribute('aria-label')).not.toMatch(/past target/);
    expect(screen.getAllByText('Late')).toHaveLength(1);
  });
});

describe('role dashboards', () => {
  it('CEO: portfolio health and open risks by project come from execution health', async () => {
    rolesApi.getCEODashboard.mockResolvedValue({
      delivery_confidence: '64%', critical_risks: 1, active_incidents: 2,
      organization_health: { total_projects: 3 },
    });
    rolesApi.getExecutionHealth.mockResolvedValue({
      total_projects: 3,
      projects: [
        { project_id: 'P1', name: 'Atlas', open_risks: 0, critical_risks: 0 },
        { project_id: 'P2', name: 'Beacon', open_risks: 2, critical_risks: 0 },
        { project_id: 'P3', name: 'Comet', open_risks: 4, critical_risks: 1 },
      ],
    });
    renderPage(<CEODashboardPage />);
    expect(await screen.findByRole('img', { name: /Portfolio health: No open risks 1 \(33%\), Open risks 1 \(33%\), Critical risk 1 \(33%\)/ })).toBeInTheDocument();
    expect(screen.getByLabelText('Comet: 4, 1 critical')).toBeInTheDocument();
    expect(screen.getByText('1 of 3 projects risk-free · 1 critical · 2 open incidents.')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Layer 5|Layer 6/);
  });

  it('PM: schedule, delivery confidence and status counts', async () => {
    rolesApi.getPMDashboard.mockResolvedValue({ projects: [
      { id: 'P1', name: 'Atlas', status: 'active', start_date: '2026-01-01', end_date: '2027-01-01' },
      { id: 'P2', name: 'Beacon', status: 'completed' },
    ], summary: { delivery_confidence: '82%', active_sprints: 2, high_risks: 0 } });
    rolesApi.getPMBlockedWork.mockResolvedValue({ counts: {}, tasks: [], matched: 0 });
    renderPage(<PMDashboardPage />);
    expect(await screen.findByRole('meter', { name: 'Delivery confidence' })).toHaveAttribute('aria-valuenow', '82');
    expect(screen.getByLabelText(/^Atlas: /)).toBeInTheDocument();
    expect(screen.getByLabelText('Completed: 1')).toBeInTheDocument();
  });

  it('Lead: review queue by risk and by author', async () => {
    rolesApi.getLeadDashboard.mockResolvedValue({
      team_id: 'TEAM-A',
      summary: { team_size: 2, open_prs: 3, high_risk_prs: 1, blocked_tasks: 0 },
      team_members: [{ employee_id: 'EMP-1', name: 'Asha Rao', role: 'DEVELOPER' }, { employee_id: 'EMP-2', name: 'Ravi Kumar', role: 'DEVELOPER' }],
      pr_review_queue: [
        { id: 1, title: 'A', author_id: 'EMP-1', risk_level: 'LOW' },
        { id: 2, title: 'B', author_id: 'EMP-1', risk_level: 'HIGH' },
        { id: 3, title: 'C', author_id: 'EMP-2', risk_level: 'LOW' },
      ],
      blockers: [],
    });
    renderPage(<LeadDashboardPage />);
    expect(await screen.findByRole('img', { name: /Review queue by risk: Low 2 \(67%\), Medium 0 \(0%\), High 1 \(33%\)/ })).toBeInTheDocument();
    expect(screen.getByLabelText('Asha Rao: 2')).toBeInTheDocument();
  });

  it('Developer: tasks by status include the ones that are neither done, in progress nor blocked', async () => {
    useAuthStore.setState({ user: roleUser('DEVELOPER', { employee_id: 'EMP-1', name: 'Asha Rao' }), token: 't', isAuthenticated: true });
    rolesApi.getDeveloperDashboard.mockResolvedValue({
      summary: { total_tasks: 10, completed_tasks: 4, in_progress_tasks: 3, blocked_tasks: 1, open_prs: 1 },
      my_tasks: [], my_prs: [{ id: 1, title: 'Fix login', risk_level: 'MEDIUM' }],
    });
    performanceApi.getDeveloperDashboard.mockResolvedValue({ current_performance: null });
    renderPage(<DeveloperDashboardPage />);
    expect(await screen.findByRole('img', { name: /My tasks by status: Done 4 \(40%\), In progress 3 \(30%\), Blocked 1 \(10%\), To do and other 2 \(20%\)/ })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /My open pull requests by risk: .*Medium 1 \(100%\)/ })).toBeInTheDocument();
  });

  it('QA: daily outcomes, pass rate and coverage from the QA dashboard', async () => {
    useAuthStore.setState({ user: roleUser('QA'), token: 't', isAuthenticated: true });
    qaApi.getProjects.mockResolvedValue([{ id: 'P1', name: 'Atlas' }]);
    qaApi.getCIConfigs.mockResolvedValue({ configs: [] });
    qaApi.getTestRuns.mockResolvedValue({ runs: [] });
    qaApi.getDashboard.mockResolvedValue({
      total_test_cases: 10, not_executed: 4, total_executions: 9, passed: 6, failed: 2, blocked: 1, pass_rate: 75,
      open_defects: 1, awaiting_retest: 0, recent_executions: [],
      execution_trend: [{ date: '2026-11-13', passed: 4, failed: 1, blocked: 0 }, { date: '2026-11-14', passed: 2, failed: 1, blocked: 1 }],
    });
    renderPage(<QADashboardPage />);
    expect(await screen.findByRole('meter', { name: 'Pass rate' })).toHaveAttribute('aria-valuenow', '75');
    expect(screen.getByRole('img', { name: 'Executions per day, 2 days' })).toBeInTheDocument(); // consecutive days
    expect(screen.getByRole('img', { name: /Test case coverage: Run at least once 6 \(60%\), Not run yet 4 \(40%\)/ })).toBeInTheDocument();
  });

  it('DevOps shows distinct workflow attempts and links to deployment evidence', async () => {
    rolesApi.getDevOpsDashboard.mockResolvedValue({
      summary: { build_success_rate: 50, workflow_attempts: 2, deployments_today: 1, active_incidents: 3 },
      outcomes: { success: 1, failed: 1 },
      daily: [{ date: '2026-11-23', success: 1, failed: 1 }],
      pipelines: [{ id: 42, attempt: 2, name: 'CI', repository: 'org/app', conclusion: 'success' }],
      deployments: [{ id: 7, environment: 'production', repository: 'org/app', status: 'success' }],
    });
    renderPage(<DevOpsDashboardPage />);
    expect(await screen.findByRole('button', { name: 'Succeeded: 1' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /CI #42/ })).toHaveAttribute('href', 'https://github.com/org/app/actions/runs/42/attempts/2');
    expect(screen.getByRole('link', { name: /org\/app #7/ })).toHaveAttribute('href', '/deployments?repository=org%2Fapp&deployment_id=7');
    expect(screen.getByRole('group', { name: /Workflow attempts by day/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open incidents' })).toBeInTheDocument();
  });

  it('HR: workforce by role and department, and who is not in a team', async () => {
    rolesApi.getHRDashboard.mockResolvedValue({
      summary: { total_employees: 4, role_distribution: { DEVELOPER: 2, CEO: 1, HR: 1 } },
      employees: [
        { employee_id: 'EMP-1', name: 'Asha Rao', role: 'DEVELOPER', dept: 'Engineering', team_id: 'TEAM-A' },
        { employee_id: 'EMP-2', name: 'Ravi Kumar', role: 'DEVELOPER', dept: 'Engineering' },
        { employee_id: 'EMP-3', name: 'Meera Iyer', role: 'CEO', dept: 'Executive' },
        { employee_id: 'EMP-4', name: 'John Paul', role: 'HR', dept: 'People & Culture' },
      ],
    });
    transfersApi.getTransfers.mockResolvedValue([]);
    renderPage(<HRDashboardPage />);
    expect(await screen.findByLabelText('Engineering: 2')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Team placement: In a team 1 \(50%\), Not in a team 1 \(50%\)/ })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Talent Growth Index|Performance Average/);
  });
});
