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
const SetupPage = React.lazy(() =>
  import('../pages/auth/SetupPage').then((m) => ({ default: m.SetupPage }))
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
const CEOQualityPage = React.lazy(() =>
  import('../pages/ceo/CEOQualityPage').then((m) => ({
    default: m.CEOQualityPage,
  }))
);
const CEORiskPage = React.lazy(() =>
  import('../pages/ceo/CEORiskPage').then((m) => ({
    default: m.CEORiskPage,
  }))
);
const CEOOrganizationPage = React.lazy(() =>
  import('../pages/ceo/CEOOrganizationPage').then((m) => ({
    default: m.CEOOrganizationPage,
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
const TransferRequestsPage = React.lazy(() =>
  import('../pages/transfers/TransferRequestsPage').then((m) => ({
    default: m.TransferRequestsPage,
  }))
);
const TransferRequestForm = React.lazy(() =>
  import('../pages/transfers/TransferRequestForm').then((m) => ({
    default: m.TransferRequestForm,
  }))
);
const TransferDetailPage = React.lazy(() =>
  import('../pages/transfers/TransferDetailPage').then((m) => ({
    default: m.TransferDetailPage,
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
const ApprovalsPage = React.lazy(() =>
  import('../pages/approvals/ApprovalsPage').then((m) => ({
    default: m.ApprovalsPage,
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
        <Route path="/setup" element={<SetupPage />} />

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
          {Object.values(ROLES).map((role) => (
            <Route
              key={role}
              path={role.toLowerCase()}
              element={<Navigate to={`/${role.toLowerCase()}/dashboard`} replace />}
            />
          ))}
          <Route path="github" element={<Navigate to="/github/sync" replace />} />
          <Route
            path="developer/dashboard"
            element={
              <RoleGuard page="developerDashboard">
                <DeveloperDashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="lead/dashboard"
            element={
              <RoleGuard page="leadDashboard">
                <LeadDashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="pm/dashboard"
            element={
              <RoleGuard page="pmDashboard">
                <PMDashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="qa/dashboard"
            element={
              <RoleGuard page="qaDashboard">
                <QADashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="devops/dashboard"
            element={
              <RoleGuard page="devopsDashboard">
                <DevOpsDashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="hr/dashboard"
            element={
              <RoleGuard page="hrDashboard">
                <HRDashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="ceo/dashboard"
            element={
              <RoleGuard page="ceoDashboard">
                <CEODashboardPage />
              </RoleGuard>
            }
          />
          <Route
            path="quality"
            element={
              <RoleGuard page="ceoQuality">
                <CEOQualityPage />
              </RoleGuard>
            }
          />
          <Route
            path="risk"
            element={
              <RoleGuard page="ceoRisk">
                <CEORiskPage />
              </RoleGuard>
            }
          />
          <Route
            path="organization"
            element={
              <RoleGuard page="ceoOrganization">
                <CEOOrganizationPage />
              </RoleGuard>
            }
          />

          {/* Work Management */}
          <Route path="projects" element={<RoleGuard page="projects"><ProjectsPage /></RoleGuard>} />
          <Route path="projects/:projectId" element={<RoleGuard page="projects"><ProjectDetailPage /></RoleGuard>} />
          <Route path="teams" element={<RoleGuard page="teams"><TeamsPage /></RoleGuard>} />
          <Route path="teams/:teamId" element={<RoleGuard page="teamDetail"><TeamDetailPage /></RoleGuard>} />
          <Route
            path="employees"
            element={
              <RoleGuard page="employees">
                <EmployeesPage />
              </RoleGuard>
            }
          />
          <Route
            path="transfers"
            element={
              <RoleGuard page="transfers">
                <TransferRequestsPage />
              </RoleGuard>
            }
          />
          <Route
            path="transfers/new"
            element={
              <RoleGuard page="transfers">
                <TransferRequestForm />
              </RoleGuard>
            }
          />
          <Route
            path="transfers/:transferId"
            element={
              <RoleGuard page="transfers">
                <TransferDetailPage />
              </RoleGuard>
            }
          />
          <Route path="sprints" element={<RoleGuard page="sprints"><SprintsPage /></RoleGuard>} />
          <Route path="sprints/:sprintId" element={<RoleGuard page="sprints"><SprintsPage /></RoleGuard>} />
          <Route path="tasks" element={<RoleGuard page="tasks"><TasksPage /></RoleGuard>} />
          <Route path="board" element={<RoleGuard page="board"><BoardPage /></RoleGuard>} />

          {/* Intelligence & Engineering */}
          <Route path="code-quality" element={<RoleGuard page="codeQuality"><CodeQualityPage /></RoleGuard>} />
          <Route path="code-quality/runs/:runId" element={<RoleGuard page="codeQuality"><RunDetailPage /></RoleGuard>} />
          <Route path="github/sync" element={<RoleGuard page="githubSync"><GitHubSyncPage /></RoleGuard>} />
          <Route path="pull-requests" element={<RoleGuard page="pullRequests"><PullRequestsPage /></RoleGuard>} />
          <Route path="cicd-logs" element={<RoleGuard page="cicdLogs"><CicdLogsPage /></RoleGuard>} />
          <Route
            path="evaluation"
            element={
              <RoleGuard page="evaluation">
                <AIEvaluationPage />
              </RoleGuard>
            }
          />

          {/* QA & Testing */}
          <Route
            path="tests"
            element={
              <RoleGuard page="tests">
                <TestsPage />
              </RoleGuard>
            }
          />
          <Route
            path="bugs"
            element={
              <RoleGuard page="bugs">
                <BugsPage />
              </RoleGuard>
            }
          />

          {/* Stories */}
          <Route
            path="stories"
            element={
              <RoleGuard page="stories">
                <StoriesPage />
              </RoleGuard>
            }
          />

          {/* DevOps */}
          <Route
            path="pipelines"
            element={
              <RoleGuard page="pipelines">
                <PipelinesPage />
              </RoleGuard>
            }
          />
          <Route
            path="deployments"
            element={
              <RoleGuard page="deployments">
                <DeploymentsPage />
              </RoleGuard>
            }
          />
          <Route
            path="incidents"
            element={
              <RoleGuard page="incidents">
                <IncidentsPage />
              </RoleGuard>
            }
          />

          {/* Audit Logs */}
          <Route
            path="audit"
            element={
              <RoleGuard page="audit">
                <AuditLogsPage />
              </RoleGuard>
            }
          />

          {/* Performance, Feedback & Analytics */}
          <Route path="performance" element={<RoleGuard page="performance"><PerformancePage /></RoleGuard>} />
          <Route
            path="feedback"
            element={
              <RoleGuard page="feedback">
                <FeedbackPage />
              </RoleGuard>
            }
          />
          <Route path="reports" element={<RoleGuard page="reports"><ReportsPage /></RoleGuard>} />
          {/* CR-010: two-person approval; notifications link to /approvals/{id}. */}
          <Route path="approvals" element={<RoleGuard page="approvals"><ApprovalsPage /></RoleGuard>} />
          <Route path="approvals/:approvalId" element={<RoleGuard page="approvals"><ApprovalsPage /></RoleGuard>} />
          <Route path="profile" element={<RoleGuard page="profile"><ProfilePage /></RoleGuard>} />

          {/* 404 Route */}
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
