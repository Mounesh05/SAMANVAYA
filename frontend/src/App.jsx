import { Routes, Route, Navigate } from 'react-router-dom';
import LoginStandalonePage from './pages/LoginStandalonePage';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import DashboardLayout from './components/DashboardLayout';
import HomePage from './pages/HomePage';
import CEODashboard from './pages/ceo/CEODashboard';
import SprintOverview from './pages/ceo/SprintOverview';
import ExecutionHealth from './pages/ceo/ExecutionHealth';
import RiskEscalations from './pages/ceo/RiskEscalations';
import PerformanceInsights from './pages/ceo/PerformanceInsights';
import CEOReports from './pages/ceo/CEOReports';
import BacklogStories from './pages/ceo/BacklogStories';
import SprintRetrospective from './pages/ceo/SprintRetrospective';
import CEOTasks from './pages/ceo/CEOTasks';
import CEOHiring from './pages/ceo/CEOHiring';
import CEOProjects from './pages/ceo/CEOProjects';
import HRDashboard from './pages/hr/HRDashboard';
import HREmployees from './pages/hr/HREmployees';
import HRInvitations from './pages/hr/HRInvitations';
import HRPerformanceAnalytics from './pages/hr/HRPerformanceAnalytics';
import HRPromotions from './pages/hr/HRPromotions';
import HRBehaviourScores from './pages/hr/HRBehaviourScores';
import HRReports from './pages/hr/HRReports';
import HRCompanySettings from './pages/hr/HRCompanySettings';
import EmployeeProfile from './pages/hr/EmployeeProfile';
import TeamsPage from './pages/hr/TeamsPage';
import PMDashboard from './pages/pm/PMDashboard';
import PMMyTeam from './pages/pm/PMMyTeam';
import PMTasks from './pages/pm/PMTasks';
import PMReviewQueue from './pages/pm/PMReviewQueue';
import PMAlignmentReports from './pages/pm/PMAlignmentReports';
import PMWorkload from './pages/pm/PMWorkload';
import PMTeamPerformance from './pages/pm/PMTeamPerformance';
import PMRiskEscalation from './pages/pm/PMRiskEscalation';
import PMRetrospective from './pages/pm/PMRetrospective';
import LeadDashboard from './pages/lead/LeadDashboard';
import SMMyTeam from './pages/lead/SMMyTeam';
import SMSprintBoard from './pages/lead/SMSprintBoard';
import SMReviewQueue from './pages/lead/SMReviewQueue';
import SMAlignmentInsights from './pages/lead/SMAlignmentInsights';
import SMWorkload from './pages/lead/SMWorkload';
import SMTeamPerformance from './pages/lead/SMTeamPerformance';
import SMRiskBlockers from './pages/lead/SMRiskBlockers';
import SMRetrospective from './pages/lead/SMRetrospective';
import DevDashboard from './pages/developer/DevDashboard';
import DevMyTasks from './pages/developer/DevMyTasks';
import DevSprintBoard from './pages/developer/DevSprintBoard';
import DevActiveBranches from './pages/developer/DevActiveBranches';
import DevPullRequests from './pages/developer/DevPullRequests';
import DevSubmissions from './pages/developer/DevSubmissions';
import DevAIFeedback from './pages/developer/DevAIFeedback';
import DevProgressHistory from './pages/developer/DevProgressHistory';
import DevOpsDashboard from './pages/devops/DevOpsDashboard';
import DevOpsPipelines from './pages/devops/DevOpsPipelines';
import DevOpsDeployments from './pages/devops/DevOpsDeployments';
import DevOpsInfrastructure from './pages/devops/DevOpsInfrastructure';
import DevOpsLogsAlerts from './pages/devops/DevOpsLogsAlerts';
import DevOpsSystemHealth from './pages/devops/DevOpsSystemHealth';
import DevOpsTasksPage from './pages/devops/DevOpsTasksPage';
import DevOpsIncidents from './pages/devops/DevOpsIncidents';
import DevOpsReports from './pages/devops/DevOpsReports';
import QADashboard from './pages/qa/QADashboard';
import QAAssignedStories from './pages/qa/QAAssignedStories';
import QATestCases from './pages/qa/QATestCases';
import QABugReports from './pages/qa/QABugReports';
import QARegressionSuite from './pages/qa/QARegressionSuite';
import QATestRuns from './pages/qa/QATestRuns';
import QAQualityMetrics from './pages/qa/QAQualityMetrics';
import QAReleaseReadiness from './pages/qa/QAReleaseReadiness';
import QAReports from './pages/qa/QAReports';
import ProfilePage from './pages/shared/ProfilePage';
import ReportsPage from './pages/shared/ReportsPage';
import TaskManagement from './pages/shared/TaskManagement';
import GenericPage from './pages/shared/GenericPage';
import AdminPanel from './pages/admin/AdminPanel';

/* Route the /dashboard path to the correct role-specific dashboard */
function RoleDashboard() {
  const { user } = useAuth();
  const role = user?.role;
  switch (role) {
    case 'CEO': return <CEODashboard />;
    case 'HR': return <HRDashboard />;
    case 'PM': return <PMDashboard />;
    case 'LEAD': return <LeadDashboard />;
    case 'DEVELOPER': return <DevDashboard />;
    case 'DEVOPS': return <DevOpsDashboard />;
    case 'QA': return <QADashboard />;
    default: return <CEODashboard />;
  }
}

/* Render role-specific page or fallback */
function RoleRoute({ ceo, hr, pm, lead, fallback }) {
  const { user } = useAuth();
  const role = user?.role;
  if (role === 'CEO' && ceo) return ceo;
  if (role === 'HR' && hr) return hr;
  if (role === 'PM' && pm) return pm;
  if (role === 'LEAD' && lead) return lead;
  return fallback;
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public – Home page (with embedded login) */}
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginStandalonePage />} />

        {/* Protected layout */}
        <Route element={<ProtectedRoute><DashboardLayout /></ProtectedRoute>}>
          <Route path="/dashboard" element={<RoleDashboard />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/reports" element={<RoleRoute ceo={<CEOReports />} hr={<HRReports />} fallback={<ReportsPage />} />} />
          <Route path="/tasks" element={<RoleRoute ceo={<BacklogStories />} fallback={<TaskManagement />} />} />
          {/* CEO and Project routes */}
          <Route path="/projects" element={<RoleRoute ceo={<SprintOverview />} hr={<CEOProjects />} fallback={<GenericPage />} />} />
          <Route path="/execution-health" element={<RoleRoute ceo={<ExecutionHealth />} fallback={<GenericPage />} />} />
          <Route path="/escalations" element={<RoleRoute ceo={<RiskEscalations />} pm={<PMRiskEscalation />} fallback={<GenericPage />} />} />
          <Route path="/performance" element={<RoleRoute ceo={<PerformanceInsights />} fallback={<GenericPage />} />} />
          <Route path="/advisory-notes" element={<RoleRoute ceo={<SprintRetrospective />} fallback={<GenericPage />} />} />
          <Route path="/ceo-tasks" element={<RoleRoute ceo={<CEOTasks />} fallback={<GenericPage />} />} />
          <Route path="/hiring" element={<RoleRoute ceo={<CEOHiring />} hr={<HRInvitations />} fallback={<GenericPage />} />} />
          <Route path="/ceo-projects" element={<RoleRoute ceo={<CEOProjects />} hr={<CEOProjects />} fallback={<GenericPage />} />} />
          <Route path="/projects-management" element={<CEOProjects />} />
          <Route path="/backlog" element={<RoleRoute ceo={<BacklogStories />} fallback={<GenericPage />} />} />
          {/* HR-specific routes & aliases */}
          <Route path="/employees" element={<RoleRoute hr={<HREmployees />} ceo={<HREmployees />} fallback={<GenericPage />} />} />
          <Route path="/employees/:id" element={<EmployeeProfile />} />
          <Route path="/invitations" element={<RoleRoute hr={<HRInvitations />} fallback={<GenericPage />} />} />
          <Route path="/performance-analytics" element={<RoleRoute hr={<HRPerformanceAnalytics />} fallback={<GenericPage />} />} />
          <Route path="/promotions" element={<RoleRoute ceo={<HRPromotions />} hr={<HRPromotions />} fallback={<GenericPage />} />} />
          <Route path="/behavior-scores" element={<RoleRoute ceo={<HRBehaviourScores />} hr={<HRBehaviourScores />} fallback={<GenericPage />} />} />
          <Route path="/settings" element={<RoleRoute hr={<HRCompanySettings />} ceo={<HRCompanySettings />} fallback={<GenericPage />} />} />
          {/* Direct /hr/* URL aliases to guarantee zero 404s */}
          <Route path="/hr/dashboard" element={<HRDashboard />} />
          <Route path="/hr/employees" element={<HREmployees />} />
          <Route path="/hr/employees/:id" element={<EmployeeProfile />} />
          <Route path="/hr/settings" element={<HRCompanySettings />} />
          <Route path="/hr/company-settings" element={<HRCompanySettings />} />
          <Route path="/hr/reports" element={<HRReports />} />
          <Route path="/hr/performance" element={<HRPerformanceAnalytics />} />
          <Route path="/hr/performance-analytics" element={<HRPerformanceAnalytics />} />
          <Route path="/hr/promotions" element={<HRPromotions />} />
          <Route path="/hr/behavior-scores" element={<HRBehaviourScores />} />
          <Route path="/hr/invitations" element={<HRInvitations />} />
          <Route path="/hr/projects" element={<CEOProjects />} />
          <Route path="/hr/teams" element={<TeamsPage />} />
          <Route path="/ceo-teams" element={<TeamsPage />} />
          <Route path="/teams" element={<RoleRoute hr={<TeamsPage />} ceo={<TeamsPage />} pm={<PMMyTeam />} fallback={<GenericPage />} />} />
          <Route path="/approvals" element={<RoleRoute pm={<PMReviewQueue />} fallback={<GenericPage />} />} />
          <Route path="/execution-signals" element={<RoleRoute pm={<PMAlignmentReports />} fallback={<GenericPage />} />} />
          <Route path="/my-team" element={<RoleRoute lead={<SMMyTeam />} fallback={<GenericPage />} />} />
          <Route path="/sprint-board-sm" element={<RoleRoute lead={<SMSprintBoard />} fallback={<GenericPage />} />} />
          <Route path="/review-queue" element={<RoleRoute lead={<SMReviewQueue />} fallback={<GenericPage />} />} />
          <Route path="/ai-alignment" element={<RoleRoute lead={<SMAlignmentInsights />} fallback={<GenericPage />} />} />
          <Route path="/workload" element={<RoleRoute pm={<PMWorkload />} lead={<SMWorkload />} fallback={<GenericPage />} />} />
          <Route path="/team-performance" element={<RoleRoute pm={<PMTeamPerformance />} lead={<SMTeamPerformance />} fallback={<GenericPage />} />} />
          <Route path="/risk-blockers" element={<RoleRoute lead={<SMRiskBlockers />} fallback={<GenericPage />} />} />
          <Route path="/sm-retrospective" element={<RoleRoute lead={<SMRetrospective />} fallback={<GenericPage />} />} />
          <Route path="/my-tasks" element={<DevMyTasks />} />
          <Route path="/sprint-board" element={<DevSprintBoard />} />
          <Route path="/active-branches" element={<DevActiveBranches />} />
          <Route path="/pull-requests" element={<DevPullRequests />} />
          <Route path="/submissions" element={<DevSubmissions />} />
          <Route path="/ai-feedback" element={<DevAIFeedback />} />
          <Route path="/progress-history" element={<DevProgressHistory />} />
          <Route path="/pipelines" element={<DevOpsPipelines />} />
          <Route path="/deployments" element={<DevOpsDeployments />} />
          <Route path="/infrastructure" element={<DevOpsInfrastructure />} />
          <Route path="/logs-alerts" element={<DevOpsLogsAlerts />} />
          <Route path="/devops-tasks" element={<DevOpsTasksPage />} />
          <Route path="/system-health" element={<DevOpsSystemHealth />} />
          <Route path="/incidents" element={<DevOpsIncidents />} />
          <Route path="/devops-reports" element={<DevOpsReports />} />
          <Route path="/assigned-stories" element={<QAAssignedStories />} />
          <Route path="/test-cases" element={<QATestCases />} />
          <Route path="/bug-reports" element={<QABugReports />} />
          <Route path="/regression-suite" element={<QARegressionSuite />} />
          <Route path="/test-runs" element={<QATestRuns />} />
          <Route path="/quality-metrics" element={<QAQualityMetrics />} />
          <Route path="/release-readiness" element={<QAReleaseReadiness />} />
          <Route path="/qa-reports" element={<QAReports />} />
          <Route path="/pm-retrospective" element={<RoleRoute pm={<PMRetrospective />} fallback={<GenericPage />} />} />

          {/* SuperAdmin & Tenant Leadership Provisioning */}
          <Route path="/admin" element={<AdminPanel defaultTab="profile" />} />
          <Route path="/admin/profile" element={<AdminPanel defaultTab="profile" />} />
          <Route path="/admin/companies" element={<AdminPanel defaultTab="companies" />} />
          <Route path="/admin/create-company" element={<AdminPanel defaultTab="create" />} />
          <Route path="/samanvaya.admin/profile" element={<AdminPanel defaultTab="profile" />} />
        </Route>

        {/* Direct standalone access to Admin Profile */}
        <Route path="/samanvaya.admin/profile" element={<AdminPanel defaultTab="profile" />} />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;
