/**
 * PM Analytics Page — Project delivery velocity, burndown, and milestone tracking
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart3,
  TrendingUp,
  Zap,
  Clock,
  AlertTriangle,
  CheckCircle2,
  FolderKanban,
  RefreshCw,
} from 'lucide-react';
import { projectsApi } from '../../api/projects.api';
import { sprintsApi } from '../../api/sprints.api';
import { tasksApi } from '../../api/tasks.api';
import { pmAPI } from '../../services/api';
import { LoadingState, ErrorState } from '../../components/common/States';
import { MetricCard } from '../../components/common/ScoreCard';
import { StatusBadge, RiskBadge } from '../../components/common/Badges';
import { formatPercent } from '../../utils/formatters';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

export function PMAnalyticsPage() {
  const [selectedProjectId, setSelectedProjectId] = useState('ALL');

  const { data: projectsData, isLoading: loadingProjects } = useQuery({
    queryKey: ['pm-analytics-projects'],
    queryFn: () => projectsApi.list().then((r) => (Array.isArray(r.data) ? r.data : r.data?.projects || [])).catch(() => []),
  });

  const { data: tasksData } = useQuery({
    queryKey: ['pm-analytics-tasks'],
    queryFn: () => tasksApi.list().then((r) => (Array.isArray(r.data) ? r.data : r.data?.tasks || [])).catch(() => []),
  });

  const { data: analyticsData } = useQuery({
    queryKey: ['pm-analytics-metrics'],
    queryFn: () => pmAPI.analytics().catch(() => ({})),
  });

  const velocityData = analyticsData?.velocityData?.length ? analyticsData.velocityData : [];
  const burndownData = analyticsData?.burndownData?.length ? analyticsData.burndownData : [];

  const projects = projectsData || [];
  const tasks = tasksData || [];

  const completedTasks = tasks.filter((t) => t.status === 'Done' || t.status === 'Completed').length;
  const inProgressTasks = tasks.filter((t) => t.status === 'In Progress').length;
  const reviewTasks = tasks.filter((t) => t.status === 'In Review' || t.status === 'Review').length;
  const todoTasks = tasks.filter((t) => t.status === 'To Do' || t.status === 'Backlog').length;

  const taskStatusData = tasks.length > 0 ? [
    { name: 'Completed', value: completedTasks, color: 'var(--success)' },
    { name: 'In Progress', value: inProgressTasks, color: 'var(--info)' },
    { name: 'Review', value: reviewTasks, color: 'var(--warning)' },
    { name: 'To Do', value: todoTasks, color: 'var(--text-muted)' },
  ] : (analyticsData?.taskStatusData || []);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Delivery Analytics & Velocity</h1>
          <p className="page-subtitle">Project execution pace, sprint completion burndown, and allocation health</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <select
            className="form-select"
            style={{ width: 'auto' }}
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
          >
            <option value="ALL">All Active Projects</option>
            {projects.map((p) => (
              <option key={p.id || p._id} value={p.id || p._id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="metric-grid">
        <MetricCard
          label="Sprint Velocity"
          value="48.2 pts"
          icon={Zap}
          iconBg="rgba(99,102,241,0.12)"
          iconColor="var(--brand-400)"
        />
        <MetricCard
          label="On-Time Delivery"
          value="92.4%"
          icon={CheckCircle2}
          iconBg="rgba(16,185,129,0.1)"
          iconColor="var(--success)"
        />
        <MetricCard
          label="Active Story Points"
          value="65 pts"
          icon={BarChart3}
          iconBg="rgba(59,130,246,0.1)"
          iconColor="var(--info)"
        />
        <MetricCard
          label="Blocked Tasks"
          value="2 tasks"
          icon={AlertTriangle}
          iconBg="rgba(239,68,68,0.1)"
          iconColor="var(--danger)"
        />
      </div>

      {/* Charts Grid */}
      <div className="grid-2" style={{ marginBottom: 'var(--space-6)' }}>
        {/* Velocity Chart */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Sprint Velocity Trend</div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Planned vs Completed</span>
          </div>
          <div style={{ height: 260, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={velocityData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="sprint" stroke="var(--text-muted)" fontSize={12} tickLine={false} />
                <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-primary)',
                    fontSize: '0.8125rem',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }} />
                <Bar dataKey="planned" name="Planned Points" fill="var(--border-light)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="completed" name="Completed Points" fill="var(--brand-500)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Burndown Chart */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Active Sprint Burndown</div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Remaining Story Points</span>
          </div>
          <div style={{ height: 260, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={burndownData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="day" stroke="var(--text-muted)" fontSize={12} tickLine={false} />
                <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--bg-elevated)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-md)',
                    color: 'var(--text-primary)',
                    fontSize: '0.8125rem',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }} />
                <Line type="monotone" dataKey="ideal" name="Ideal Guideline" stroke="var(--text-muted)" strokeDasharray="4 4" dot={false} />
                <Line type="monotone" dataKey="actual" name="Actual Remaining" stroke="var(--warning)" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Task Distribution & Blockers */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <div className="card-title">Task Status Breakdown</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-around', height: 200 }}>
            <div style={{ width: 160, height: 160 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={taskStatusData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={75}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {taskStatusData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: '0.8125rem' }}>
              {taskStatusData.map((d) => (
                <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 10, height: 10, borderRadius: '50%', background: d.color }} />
                  <span style={{ color: 'var(--text-secondary)' }}>{d.name}:</span>
                  <strong style={{ color: 'var(--text-primary)' }}>{d.value} tasks</strong>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">Project Milestones & Delivery Risk</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            {projects.slice(0, 4).map((p, i) => (
              <div
                key={p.id || p._id || i}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: 'var(--space-3)',
                  background: 'var(--bg-elevated)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border)',
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                    {p.name}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {p.key || 'PRJ'} • Target: {p.deadline || 'End of Sprint'}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                  <StatusBadge status={p.status || 'ACTIVE'} />
                  <RiskBadge level={i === 1 ? 'MEDIUM' : 'LOW'} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
