import React, { Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { ProtectedRoute } from '../auth/ProtectedRoute';
import { RoleGuard } from '../auth/RoleGuard';
import { AppShell } from '../components/layout/AppShell';
import { ROLES } from '../utils/constants';

// ── Lazy-loaded Pages (code-split per route) ────────────────────────────────

// Auth
const LoginPage = React.lazy(() =>
  import('../pages/auth/LoginPage').then((m) => ({ default: m.LoginPage }))
);

// Role Dashboards
const DeveloperDashboardPage = React.lazy(() =>
  import('../pages/developer/DeveloperDashboardPage').then((m) => ({
    default: m.DeveloperDashboardPage,
  }))
);
const LeadDashboardPage = React.lazy(() =>
  import('../pages/lead/LeadDashboardPage').then((m) => ({
    default: m.LeadDashboardPage,
  }))
);
const PMDashboardPage = React.lazy(() =>
  import('../pages/pm/PMDashboardPage').then((m) => ({
    default: m.PMDashboardPage,
  }))
);
const QADashboardPage = React.lazy(() =>
  import('../pages/qa/QADashboardPage').then((m) => ({
    default: m.QADashboardPage,
  }))
);
const DevOpsDashboardPage = React.lazy(() =>
  import('../pages/devops/DevOpsDashboardPage').then((m) => ({
    default: m.DevOpsDashboardPage,
  }))
);
const HRDashboardPage = React.lazy(() =>
  import('../pages/hr/HRDashboardPage').then((m) => ({
    default: m.HRDashboardPage,
  }))
);
const CEODashboardPage = React.lazy(() =>
  import('../pages/ceo/CEODashboardPage').then((m) => ({
    default: m.CEODashboardPage,
  }))
);

// Work Management
const ProjectsPage = React.lazy(() =>
  import('../pages/projects/ProjectsPage').then((m) => ({
    default: m.ProjectsPage,
  }))
);
const ProjectDetailPage = React.lazy(() =>
  import('../pages/projects/ProjectDetailPage').then((m) => ({
    default: m.ProjectDetailPage,
  }))
);
const TeamsPage = React.lazy(() =>
  import('../pages/teams/TeamsPage').then((m) => ({
    default: m.TeamsPage,
  }))
);
const TeamDetailPage = React.lazy(() =>
  import('../pages/teams/TeamDetailPage').then((m) => ({
    default: m.TeamDetailPage,
  }))
);
const EmployeesPage = React.lazy(() =>
  import('../pages/employees/EmployeesPage').then((m) => ({
    default: m.EmployeesPage,
  }))
);
const SprintsPage = React.lazy(() =>
  import('../pages/sprints/SprintsPage').then((m) => ({
    default: m.SprintsPage,
  }))
);
const TasksPage = React.lazy(() =>
  import('../pages/tasks/TasksPage').then((m) => ({
    default: m.TasksPage,
  }))
);
const BoardPage = React.lazy(() =>
  import('../pages/board/BoardPage').then((m) => ({
    default: m.BoardPage,
  }))
);

// Intelligence & Engineering
const CodeQualityPage = React.lazy(() =>
  import('../pages/code-quality/CodeQualityPage').then((m) => ({
    default: m.CodeQualityPage,
  }))
);
const RunDetailPage = React.lazy(() =>
  import('../pages/code-quality/RunDetailPage').then((m) => ({
    default: m.RunDetailPage,
  }))
);
const GitHubSyncPage = React.lazy(() =>
  import('../pages/github/GitHubSyncPage').then((m) => ({
    default: m.GitHubSyncPage,
  }))
);
const CicdLogsPage = React.lazy(() =>
  import('../pages/cicd-logs/CicdLogsPage').then((m) => ({
    default: m.CicdLogsPage,
  }))
);
const AIEvaluationPage = React.lazy(() =>
  import('../pages/evaluation/AIEvaluationPage').then((m) => ({
    default: m.AIEvaluationPage,
  }))
);
const PullRequestsPage = React.lazy(() =>
  import('../pages/pull-requests/PullRequestsPage').then((m) => ({
    default: m.PullRequestsPage,
  }))
);

// QA & Testing
const BugsPage = React.lazy(() =>
  import('../pages/bugs/BugsPage').then((m) => ({
    default: m.BugsPage,
  }))
);
const TestsPage = React.lazy(() =>
  import('../pages/tests/TestsPage').then((m) => ({
    default: m.TestsPage,
  }))
);

// Stories
const StoriesPage = React.lazy(() =>
  import('../pages/stories/StoriesPage').then((m) => ({
    default: m.StoriesPage,
  }))
);

// DevOps
const PipelinesPage = React.lazy(() =>
  import('../pages/pipelines/PipelinesPage').then((m) => ({
    default: m.PipelinesPage,
  }))
);
const DeploymentsPage = React.lazy(() =>
  import('../pages/deployments/DeploymentsPage').then((m) => ({
    default: m.DeploymentsPage,
  }))
);
const IncidentsPage = React.lazy(() =>
  import('../pages/incidents/IncidentsPage').then((m) => ({
    default: m.IncidentsPage,
  }))
);

// Audit
const AuditLogsPage = React.lazy(() =>
  import('../pages/audit/AuditLogsPage').then((m) => ({
    default: m.AuditLogsPage,
  }))
);

// Performance & Analytics
const PerformancePage = React.lazy(() =>
  import('../pages/performance/PerformancePage').then((m) => ({
    default: m.PerformancePage,
  }))
);
const FeedbackPage = React.lazy(() =>
  import('../pages/feedback/FeedbackPage').then((m) => ({
    default: m.FeedbackPage,
  }))
);
const ReportsPage = React.lazy(() =>
  import('../pages/reports/ReportsPage').then((m) => ({
    default: m.ReportsPage,
  }))
);
const ProfilePage = React.lazy(() =>
  import('../pages/profile/ProfilePage').then((m) => ({
    default: m.ProfilePage,
  }))
);
const NotFoundPage = React.lazy(() =>
  import('../pages/error/NotFoundPage').then((m) => ({
    default: m.NotFoundPage,
  }))
);

// ── Loading Spinner ─────────────────────────────────────────────────────────

function RouteSpinner() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '100%',
        minHeight: '60vh',
      }}
    >
      <div
        style={{
          width: 40,
          height: 40,
          border: '3px solid rgba(139, 92, 246, 0.15)',
          borderTopColor: '#8b5cf6',
          borderRadius: '50%',
          animation: 'routeSpin 0.7s linear infinite',
        }}
      />
      <style>{`@keyframes routeSpin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// ── Root Redirector ─────────────────────────────────────────────────────────

function RootRedirect() {
  const { user, isAuthenticated } = useAuthStore();
  if (!isAuthenticated || !user) {
    return <Navigate to="/login" replace />;
  }
  const role = user?.role?.toLowerCase() || 'developer';
  return <Navigate to={`/${role}/dashboard`} replace />;
}

// ── App Routes ──────────────────────────────────────────────────────────────

export function AppRoutes() {
  return (
    <Suspense fallback={<RouteSpinner />}>
      <Routes>
        {/* Public Routes */}
        <Route path="/login" element={<LoginPage />} />

        {/* Authenticated Application Shell */}
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppShell />
            </ProtectedRoute>
          }
        >
          <Route index element={<RootRedirect />} />

          {/* 7 Role Dashboards */}
          <Route
            path="developer/dashboard"
            element={
              <RoleGuard allowedRoles={[ROLES.DEVELOPER]}>
                <DeveloperDashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="lead/dashboard"
            element={
              <RoleGuard allowedRoles={[ROLES.LEAD]}>
                <LeadDashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="pm/dashboard"
            element={
              <RoleGuard allowedRoles={[ROLES.PM]}>
                <PMDashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="qa/dashboard"
            element={
              <RoleGuard allowedRoles={[ROLES.QA]}>
                <QADashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="devops/dashboard"
            element={
              <RoleGuard allowedRoles={[ROLES.DEVOPS]}>
                <DevOpsDashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="hr/dashboard"
            element={
              <RoleGuard allowedRoles={[ROLES.HR]}>
                <HRDashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="ceo/dashboard"
            element={
              <RoleGuard allowedRoles={[ROLES.CEO]}>
                <CEODashboardPage />
              </RoleGuard>
            }
          />

          {/* Work Management */}
          <Route path="projects" element={<RoleGuard allowedRoles={[ROLES.PM, ROLES.LEAD, ROLES.DEVELOPER, ROLES.QA, ROLES.DEVOPS, ROLES.CEO, ROLES.HR]}><ProjectsPage /></RoleGuard>} />
          <Route path="projects/:projectId" element={<RoleGuard allowedRoles={[ROLES.PM, ROLES.LEAD, ROLES.DEVELOPER, ROLES.QA, ROLES.DEVOPS, ROLES.CEO, ROLES.HR]}><ProjectDetailPage /></RoleGuard>} />
          <Route path="teams" element={<RoleGuard allowedRoles={[ROLES.PM, ROLES.LEAD, ROLES.DEVELOPER, ROLES.HR, ROLES.CEO]}><TeamsPage /></RoleGuard>} />
          <Route path="teams/:teamId" element={<RoleGuard allowedRoles={[ROLES.PM, ROLES.LEAD, ROLES.DEVELOPER, ROLES.HR, ROLES.CEO]}><TeamDetailPage /></RoleGuard>} />
          <Route
            path="employees"
            element={
              <RoleGuard allowedRoles={[ROLES.HR, ROLES.CEO]}>
                <EmployeesPage />
              </RoleGuard>
            }
          />
          <Route path="sprints" element={<RoleGuard allowedRoles={[ROLES.PM, ROLES.LEAD, ROLES.DEVELOPER]}><SprintsPage /></RoleGuard>} />
          <Route path="sprints/:sprintId" element={<RoleGuard allowedRoles={[ROLES.PM, ROLES.LEAD, ROLES.DEVELOPER]}><SprintsPage /></RoleGuard>} />
          <Route path="tasks" element={<RoleGuard allowedRoles={[ROLES.PM, ROLES.LEAD, ROLES.DEVELOPER]}><TasksPage /></RoleGuard>} />
          <Route path="board" element={<RoleGuard allowedRoles={[ROLES.DEVELOPER, ROLES.LEAD, ROLES.PM]}><BoardPage /></RoleGuard>} />

          {/* Intelligence & Engineering */}
          <Route path="code-quality" element={<RoleGuard allowedRoles={[ROLES.DEVELOPER, ROLES.QA, ROLES.LEAD, ROLES.DEVOPS]}><CodeQualityPage /></RoleGuard>} />
          <Route path="code-quality/runs/:runId" element={<RoleGuard allowedRoles={[ROLES.DEVELOPER, ROLES.QA, ROLES.LEAD, ROLES.DEVOPS]}><RunDetailPage /></RoleGuard>} />
          <Route path="github/sync" element={<RoleGuard allowedRoles={[ROLES.DEVELOPER, ROLES.LEAD, ROLES.DEVOPS]}><GitHubSyncPage /></RoleGuard>} />
          <Route path="pull-requests" element={<RoleGuard allowedRoles={[ROLES.DEVELOPER, ROLES.LEAD, ROLES.QA, ROLES.DEVOPS]}><PullRequestsPage /></RoleGuard>} />
          <Route path="cicd-logs" element={<RoleGuard allowedRoles={[ROLES.DEVELOPER, ROLES.QA, ROLES.LEAD, ROLES.DEVOPS]}><CicdLogsPage /></RoleGuard>} />
          <Route
            path="evaluation"
            element={
              <RoleGuard allowedRoles={[ROLES.CEO, ROLES.HR, ROLES.LEAD]}>
                <AIEvaluationPage />
              </RoleGuard>
            }
          />

          {/* QA & Testing */}
          <Route
            path="tests"
            element={
              <RoleGuard allowedRoles={[ROLES.QA]}>
                <TestsPage />
              </RoleGuard>
            }
          />
          <Route
            path="bugs"
            element={
              <RoleGuard allowedRoles={[ROLES.QA]}>
                <BugsPage />
              </RoleGuard>
            }
          />

          {/* Stories */}
          <Route
            path="stories"
            element={
              <RoleGuard allowedRoles={[ROLES.PM, ROLES.LEAD, ROLES.DEVELOPER]}>
                <StoriesPage />
              </RoleGuard>
            }
          />

          {/* DevOps */}
          <Route
            path="pipelines"
            element={
              <RoleGuard allowedRoles={[ROLES.DEVOPS, ROLES.QA, ROLES.LEAD]}>
                <PipelinesPage />
              </RoleGuard>
            }
          />
          <Route
            path="deployments"
            element={
              <RoleGuard allowedRoles={[ROLES.DEVOPS, ROLES.LEAD]}>
                <DeploymentsPage />
              </RoleGuard>
            }
          />
          <Route
            path="incidents"
            element={
              <RoleGuard allowedRoles={[ROLES.DEVOPS, ROLES.LEAD, ROLES.CEO]}>
                <IncidentsPage />
              </RoleGuard>
            }
          />

          {/* Audit Logs */}
          <Route
            path="audit"
            element={
              <RoleGuard allowedRoles={[ROLES.HR, ROLES.CEO]}>
                <AuditLogsPage />
              </RoleGuard>
            }
          />

          {/* Performance, Feedback & Analytics */}
          <Route path="performance" element={<PerformancePage />} />
          <Route
            path="feedback"
            element={
              <RoleGuard
                allowedRoles={[
                  ROLES.LEAD,
                  ROLES.PM,
                  ROLES.QA,
                  ROLES.DEVOPS,
                  ROLES.HR,
                  ROLES.CEO,
                ]}
              >
                <FeedbackPage />
              </RoleGuard>
            }
          />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="profile" element={<ProfilePage />} />

          {/* 404 Route */}
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
