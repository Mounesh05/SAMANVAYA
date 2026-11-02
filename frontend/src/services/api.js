/* ── API Service ──
   Central utility for all backend calls.
   Base URL points to FastAPI server running on port 8000.
*/

const API_BASE = 'http://localhost:8000/api';

async function request(path, options = {}) {
    const url = `${API_BASE}${path}`;
    let token = sessionStorage.getItem('token');
    if (!token) {
        try {
            const saved = sessionStorage.getItem('exec_user');
            if (saved) {
                const u = JSON.parse(saved);
                token = u.token || u.access_token;
            }
        } catch (e) { }
    }
    const authHeaders = token ? { 'Authorization': `Bearer ${token}` } : {};
    const config = {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...authHeaders,
            ...(options.headers || {}),
        },
    };
    const res = await fetch(url, config);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'API request failed');
    }
    return res.json();
}

/* ── Auth ── */
export const authAPI = {
    login: (employee_id, organisation_password, employee_password) =>
        request('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ employee_id, organisation_password, employee_password }),
        }),
};

/* ── Users ── */
export const usersAPI = {
    getAll: () => request('/users'),
    getById: (id) => request(`/users/${id}`),
    update: (id, data) => request(`/users/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    updatePAT: (id, pat) => request(`/users/${id}/pat`, { method: 'PUT', body: JSON.stringify({ github_pat: pat }) }),
};

/* ── Employees ── */
export const employeesAPI = {
    getAll: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/employees${qs ? '?' + qs : ''}`);
    },
    getById: (id) => request(`/employees/${id}`),
    create: (data) => request('/employees', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/employees/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    transferTeam: (id, data) => request(`/employees/${id}/transfer-team`, { method: 'PUT', body: JSON.stringify(data) }),
};

/* ── Teams ── */
export const teamsAPI = {
    getAll: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/teams${qs ? '?' + qs : ''}`);
    },
    getById: (id) => request(`/teams/${id}`),
    getMembers: (id) => request(`/teams/${id}/members`),
    create: (data) => request('/teams', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/teams/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id) => request(`/teams/${id}`, { method: 'DELETE' }),
    addMember: (teamId, employeeId) => request(`/teams/${teamId}/members/${employeeId}`, { method: 'POST' }),
    removeMember: (teamId, employeeId) => request(`/teams/${teamId}/members/${employeeId}`, { method: 'DELETE' }),
    assignLead: (teamId, employeeId) => request(`/teams/${teamId}/assign-lead`, { method: 'POST', body: JSON.stringify({ employee_id: employeeId }) }),
};

/* ── Sprints ── */
export const sprintsAPI = {
    getAll: () => request('/sprints'),
    getById: (id) => request(`/sprints/${id}`),
    getStories: (id) => request(`/sprints/${id}/stories`),
    create: (data) => request('/sprints', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/sprints/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
};

/* ── Stories ── */
export const storiesAPI = {
    getAll: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/stories${qs ? '?' + qs : ''}`);
    },
    getById: (id) => request(`/stories/${id}`),
    create: (data) => request('/stories', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/stories/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
};

/* ── Tasks ── */
export const tasksAPI = {
    getAll: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/tasks${qs ? '?' + qs : ''}`);
    },
    getById: (id) => request(`/tasks/${id}`),
    create: (data) => request('/tasks', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/tasks/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id) => request(`/tasks/${id}`, { method: 'DELETE' }),
    // ── Workflow ──
    markDone: (id, data = {}) => request(`/tasks/${id}/mark-done`, { method: 'POST', body: JSON.stringify(data) }),
    approve: (id, data = {}) => request(`/tasks/${id}/approve`, { method: 'POST', body: JSON.stringify(data) }),
    reject: (id, data = {}) => request(`/tasks/${id}/reject`, { method: 'POST', body: JSON.stringify(data) }),
};

/* ── Projects ── */
export const projectsAPI = {
    getAll: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/projects${qs ? '?' + qs : ''}`);
    },
    getById: (id) => request(`/projects/${id}`),
    create: (data) => request('/projects', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/projects/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id, performed_by) => {
        const qs = performed_by ? `?performed_by=${encodeURIComponent(performed_by)}` : '';
        return request(`/projects/${id}${qs}`, { method: 'DELETE' });
    },
};

/* ── Candidates ── */
export const candidatesAPI = {
    getAll: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/candidates${qs ? '?' + qs : ''}`);
    },
    create: (data) => request('/candidates', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/candidates/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id) => request(`/candidates/${id}`, { method: 'DELETE' }),
};

/* ── Pipelines ── */
export const pipelinesAPI = {
    getAll: () => request('/pipelines'),
    create: (data) => request('/pipelines', { method: 'POST', body: JSON.stringify(data) }),
};

/* ── Deployments ── */
export const deploymentsAPI = {
    getAll: () => request('/deployments'),
    list: () => request('/deployments'),
    create: (data) => request('/deployments', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/deployments/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    rollback: (id) => request(`/deployments/${id}/rollback`, { method: 'POST' }),
    metrics: () => request('/deployments/metrics'),
};

/* ── System Health ── */
export const systemHealthAPI = {
    getAll: () => request('/system-health'),
};

/* ── Alerts ── */
export const alertsAPI = {
    getAll: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/alerts${qs ? '?' + qs : ''}`);
    },
    delete: (id) => request(`/alerts/${id}`, { method: 'DELETE' }),
};

/* ── Bugs ── */
export const bugsAPI = {
    getAll: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/bugs${qs ? '?' + qs : ''}`);
    },
    create: (data) => request('/bugs', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/bugs/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
};

/* ── Reports ── */
export const reportsAPI = {
    getAll: (params = {}) => {
        let queryParams = params;
        if (typeof params === 'string') {
            queryParams = { role: params };
        }
        const qs = new URLSearchParams(queryParams).toString();
        return request(`/reports${qs ? '?' + qs : ''}`);
    },
    getMetrics: () => request('/reports/metrics'),
    create: (data) => request('/reports', { method: 'POST', body: JSON.stringify(data) }),
    exportPdf: async (report, role = 'CEO', companyId = 'ORG-001') => {
        const payload = {
            id: report.id,
            title: report.title,
            role: role,
            company_id: companyId
        };
        const token = sessionStorage.getItem('token');
        const res = await fetch(`${API_BASE}/reports/export-pdf?role=${encodeURIComponent(role)}&company_id=${encodeURIComponent(companyId)}&verbose=true`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            },
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            throw new Error(`Export failed: ${res.statusText}`);
        }
        const blob = await res.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `${(report.id || 'report').toLowerCase()}-${role.toLowerCase()}-analysis.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(downloadUrl);
        document.body.removeChild(a);
        return true;
    }
};


/* ── Review Queue ── */
export const reviewQueueAPI = {
    getAll: () => request('/review-queue'),
    action: (id, data) =>
        request(`/review-queue/${id}/action`, { method: 'PUT', body: JSON.stringify(data) }),
};

/* ── Escalations ── */
export const escalationsAPI = {
    getAll: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/escalations${qs ? '?' + qs : ''}`);
    },
    create: (data) => request('/escalations', { method: 'POST', body: JSON.stringify(data) }),
};

/* ── Dashboard (aggregated) ── */
export const dashboardAPI = {
    ceo: () => request('/dashboard/ceo'),
    pm: () => request('/dashboard/pm'),
    lead: () => request('/dashboard/lead'),
    developer: (name) =>
        request(`/dashboard/developer${name ? '?user_name=' + encodeURIComponent(name) : ''}`),
    devops: () => request('/dashboard/devops'),
    qa: () => request('/dashboard/qa'),
    hr: () => request('/dashboard/hr'),
};

/* ── AI Agent ── */
export const aiAPI = {
    run: (taskType, payload = {}) =>
        request('/ai/run', { method: 'POST', body: JSON.stringify({ task_type: taskType, payload }) }),
    getResults: (taskType, limit = 20) => {
        const params = new URLSearchParams();
        if (taskType) params.set('task_type', taskType);
        params.set('limit', limit);
        return request(`/ai/results?${params.toString()}`);
    },
};

/* ── CEO API ── */
export const ceoAPI = {
    // CEODashboard.jsx
    executionWeeks: () => request('/ceo/execution-weeks'),
    sprintStatus: () => request('/ceo/sprint-status'),
    escalations: () => request('/ceo/escalations'),
    // ExecutionHealth.jsx
    healthFactors: () => request('/ceo/health-factors'),
    storyRisks: () => request('/ceo/story-risks'),
    // RiskEscalations.jsx
    activeRisks: () => request('/ceo/active-risks'),
    escalationEvents: () => request('/ceo/escalation-events'),
    riskPatterns: () => request('/ceo/risk-patterns'),
    // PerformanceInsights.jsx
    performanceMembers: () => request('/ceo/performance-members'),
    saveBehaviourScores: (data) =>
        request('/ceo/behaviour-feedback', { method: 'POST', body: JSON.stringify(data) }),
    // ExecutionHealth.jsx
    devRiskContribution: () => request('/ceo/dev-risk'),
    // SprintRetrospective.jsx
    improvements: () => request('/ceo/improvements'),
    behaviourFeedback: () => request('/ceo/behaviour-feedback'),
    generateRetrospective: () => request('/ai/retrospective', { method: 'POST' }),
};

/* ── PM API ── */
export const pmAPI = {
    // PMWorkload.jsx
    workload: () => request('/pm/workload'),
    updateWorkload: (id, data) =>
        request(`/pm/workload/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    redistributeWorkload: (data) =>
        request('/pm/workload/redistribute', { method: 'POST', body: JSON.stringify(data) }),
    // PMRiskEscalation.jsx
    escalationEvents: () => request('/pm/escalations'),
    highRiskMembers: () => request('/pm/high-risk-members'),
    // PMRetrospective.jsx
    retroSummary: () => request('/pm/retro-summary'),
    improvements: () => request('/pm/improvements'),
    aiSuggestions: () => request('/pm/ai-suggestions'),
    generateRetrospective: () => request('/pm/generate-retro', { method: 'POST' }),
    // PMMyTeam.jsx
    team: () => request('/employees'),
    // PMTeamPerformance.jsx
    teamPerformance: () => request('/ceo/performance-members'),
    // PMReviewQueue.jsx
    reviewQueue: () => request('/review-queue'),
    updateReviewItem: (id, data) =>
        request(`/review-queue/${id}/action`, { method: 'PUT', body: JSON.stringify(data) }),
    // PMAlignmentReports.jsx
    alignmentReports: () => request('/lead/alignment/breakdown'),
    alignmentTrend: () => request('/pm/alignment-trend'),
    alignmentReview: () => request('/pm/alignment-review', { method: 'POST' }),
    // PMRiskEscalation.jsx (delay distribution)
    delayDistribution: () => request('/pm/delay-dist'),
    // PMAnalyticsPage.jsx
    analytics: () => request('/pm/analytics'),
};

/* ── Lead / Scrum Master API ── */
export const leadAPI = {
    // LeadDashboard.jsx
    dashboardTeamMembers: () => request('/lead/dashboard/team-members'),
    dashboardWorkloadChart: () => request('/lead/dashboard/workload-chart'),
    dashboardPerfTrend: () => request('/lead/dashboard/perf-trend'),
    dashboardReviewQueue: () => request('/lead/dashboard/review-queue'),
    // SMSprintBoard.jsx
    sprintBoard: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/lead/sprint-board${qs ? '?' + qs : ''}`);
    },
    createStory: (data) => request('/lead/sprint-board', { method: 'POST', body: JSON.stringify(data) }),
    updateStory: (id, data) =>
        request(`/lead/sprint-board/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    // SMRetrospective.jsx
    retrospective: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/lead/retrospective${qs ? '?' + qs : ''}`);
    },
    saveRetrospective: (data) =>
        request('/lead/retrospective', { method: 'POST', body: JSON.stringify(data) }),
    updateRetrospective: (id, data) =>
        request(`/lead/retrospective/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    generateRetrospective: () => request('/lead/generate-retro', { method: 'POST' }),
    // SMMyTeam.jsx
    myTeam: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/lead/my-team${qs ? '?' + qs : ''}`);
    },
    // SMAlignmentInsights.jsx
    alignmentBreakdown: () => request('/lead/alignment/breakdown'),
    lowAlignmentStories: () => request('/lead/alignment/low-stories'),
    alignmentTrend: () => request('/lead/alignment/trend'),
    alignmentInsights: async () => {
        const [alignment_breakdown, low_alignment_stories, trend_data] = await Promise.all([
            request('/lead/alignment/breakdown').catch(() => []),
            request('/lead/alignment/low-stories').catch(() => []),
            request('/lead/alignment/trend').catch(() => []),
        ]);
        return { alignment_breakdown, low_alignment_stories, trend_data };
    },
    // SMMyTeam.jsx
    myTeam: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/lead/my-team${qs ? '?' + qs : ''}`);
    },
    teamMember: (id) => request(`/lead/my-team/${id}`),
    // SMReviewQueue.jsx
    reviewQueue: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/lead/review-queue${qs ? '?' + qs : ''}`);
    },
    updateReviewItem: (id, data) =>
        request(`/lead/review-queue/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    // SMRiskBlockers.jsx
    blockers: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/lead/blockers${qs ? '?' + qs : ''}`);
    },
    riskBlockers: () => request('/lead/blockers'),
    updateBlocker: (id, data) =>
        request(`/lead/blockers/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    // SMTeamPerformance.jsx
    performanceMembers: () => request('/lead/performance/members'),
    sprintTrend: () => request('/lead/performance/sprint-trend'),
    teamPerformance: async () => {
        const [member_perf, sprint_trend] = await Promise.all([
            request('/lead/performance/members').catch(() => []),
            request('/lead/performance/sprint-trend').catch(() => []),
        ]);
        return { member_perf, sprint_trend };
    },
    // SMWorkload.jsx
    workload: async () => {
        const [workload_data, suggestions] = await Promise.all([
            request('/lead/workload').catch(() => []),
            request('/lead/workload/suggestions').catch(() => []),
        ]);
        return { workload_data, suggestions };
    },
    workloadSuggestions: () => request('/lead/workload/suggestions'),
    updateWorkload: (name, data) =>
        request(`/lead/workload/${encodeURIComponent(name)}`, { method: 'PUT', body: JSON.stringify(data) }),
    redistributeWorkload: (data) =>
        request('/lead/workload/redistribute', { method: 'POST', body: JSON.stringify(data) }),
};

/* ── Developer API ── */
export const devAPI = {
    // DevMyTasks.jsx
    myTasks: () => request('/tasks'),
    updateTask: (id, data) => request(`/tasks/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    markDone: (id, data = {}) => request(`/tasks/${id}/mark-done`, { method: 'POST', body: JSON.stringify(data) }),
    // DevSprintBoard.jsx
    sprintBoard: () => request('/stories'),
    updateStory: (id, data) => request(`/stories/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    // DevPullRequests.jsx
    pullRequests: () => request('/dev/pull-requests'),
    createPullRequest: (data) => request('/dev/pull-requests', { method: 'POST', body: JSON.stringify(data) }),
    updatePullRequest: (id, data) => request(`/dev/pull-requests/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    // DevActiveBranches.jsx
    activeBranches: () => request('/dev/branches'),
    branches: () => request('/dev/branches'),
    // DevSubmissions.jsx
    submissions: () => request('/dev/submissions'),
    createSubmission: (data) => request('/dev/submissions', { method: 'POST', body: JSON.stringify(data) }),
    updateSubmission: (id, data) => request(`/dev/submissions/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    // DevProgressHistory.jsx
    progressHistory: () => request('/dev/progress-history'),
    // DevAIFeedback.jsx
    aiFeedback: () => request('/dev/ai-feedback'),
    generateCodeReview: () => request('/dev/generate-code-review', { method: 'POST' }),
};

/* ── DevOps API ── */
export const devopsAPI = {
    // DevOpsDeployments.jsx
    deployments: () => request('/deployments'),
    deployMetrics: () => request('/deployments/metrics'),
    rollbackDeployment: (id) => request(`/deployments/${id}/rollback`, { method: 'POST' }),
    // DevOpsIncidents.jsx
    incidents: () => request('/devops/incidents'),
    createIncident: (data) => request('/devops/incidents', { method: 'POST', body: JSON.stringify(data) }),
    // DevOpsInfrastructure.jsx
    infrastructure: () => request('/devops/infra-changes'),
    infraChanges: () => request('/devops/infra-changes'),
    createInfraChange: (data) => request('/devops/infra-changes', { method: 'POST', body: JSON.stringify(data) }),
    // DevOpsLogsAlerts.jsx
    logsAlerts: () => request('/devops/logs'),
    logsMetrics: () => request('/devops/logs/metrics'),
    // DevOpsPipelines.jsx
    pipelines: () => request('/pipelines'),
    pipelineMetrics: () => request('/pipelines/metrics'),
    triggerPipeline: (data) => request('/pipelines', { method: 'POST', body: JSON.stringify(data) }),
    // DevOpsReports.jsx
    reports: () => request('/devops/reports'),
    // DevOpsSystemHealth.jsx
    systemHealth: () => request('/system-health'),
    // DevOpsTasksPage.jsx
    tasks: () => request('/devops/devops-tasks'),
    updateTask: (id, data) => request(`/devops/devops-tasks/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    markDone: (id, data = {}) => request(`/devops/devops-tasks/${id}/mark-done`, { method: 'POST', body: JSON.stringify(data) }),
    // Ops Reviewer AI Agent
    opsReview: () => request('/devops/ops-review'),
    generateOpsReview: () => request('/devops/generate-ops-review', { method: 'POST' }),
};



/* ── QA API ── */
export const qaAPI = {
    // QATestCases.jsx
    testCases: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/qa/test-cases${qs ? '?' + qs : ''}`);
    },
    updateTestCase: (id, data) =>
        request(`/qa/test-cases/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    // QABugReports.jsx
    bugs: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/qa/bugs-qa${qs ? '?' + qs : ''}`);
    },
    bugReports: () => request('/qa/bugs-qa'),
    createBug: (data) => request('/qa/bugs-qa', { method: 'POST', body: JSON.stringify(data) }),
    // QAAssignedStories.jsx
    assignedStories: () => request('/qa/assigned-stories'),
    updateAssignedStory: (id, data) =>
        request(`/qa/assigned-stories/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    // QARegressionSuite.jsx
    regressionSuites: () => request('/qa/regression'),
    regressionSuite: () => request('/qa/regression'),
    // QAReleaseReadiness.jsx
    releaseChecks: () => request('/qa/release-checks'),
    releaseReadiness: async () => {
        const [release_checks, blocking_bugs] = await Promise.all([
            request('/qa/release-checks').catch(() => []),
            request('/qa/blocking-bugs').catch(() => []),
        ]);
        return { release_checks, blocking_bugs };
    },
    blockingBugs: () => request('/qa/blocking-bugs'),
    // QAQualityMetrics.jsx
    qualityMetrics: () => request('/qa/quality-metrics'),
    // QATestRuns.jsx
    testRuns: () => request('/qa/test-runs'),
    // QAReports.jsx
    reports: () => request('/qa/reports'),
    // QARegressionSuite.jsx
    regressionMetrics: () => request('/qa/regression-metrics'),
};

/* ── HR API ── */
export const hrAPI = {
    // HRBehaviourScores.jsx
    behaviourHistory: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/hr/behaviour/history${qs ? '?' + qs : ''}`);
    },
    behaviourRatings: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/hr/behaviour/ratings${qs ? '?' + qs : ''}`);
    },
    submitBehaviourRating: (data) =>
        request('/hr/behaviour/ratings', { method: 'POST', body: JSON.stringify(data) }),
    // HRInvitations.jsx (candidates)
    hrCandidates: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/hr/candidates${qs ? '?' + qs : ''}`);
    },
    createCandidate: (data) =>
        request('/hr/candidates', { method: 'POST', body: JSON.stringify(data) }),
    updateCandidate: (id, data) =>
        request(`/hr/candidates/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteCandidate: (id) =>
        request(`/hr/candidates/${id}`, { method: 'DELETE' }),
    // HRPerformanceAnalytics.jsx
    deptPerformance: () => request('/hr/performance/dept'),
    sprintVelocity: () => request('/hr/performance/velocity'),
    performers: (params = {}) => {
        const qs = new URLSearchParams(params).toString();
        return request(`/hr/performance/performers${qs ? '?' + qs : ''}`);
    },
    // HRReports.jsx
    auditLog: () => request('/hr/audit-log'),
    createAuditLog: (data) =>
        request('/hr/audit-log', { method: 'POST', body: JSON.stringify(data) }),
    hrReports: () => request('/hr/reports'),
    // HRCompanySettings.jsx
    companySettings: () => request('/hr/company-settings'),
    updateCompanySettings: (data) =>
        request('/hr/company-settings', { method: 'PUT', body: JSON.stringify(data) }),
};

/* ── Companies API (multi-tenant) ── */
export const companiesAPI = {
    getAll: () => request('/companies'),
    getById: (id) => request(`/companies/${id}`),
    create: (data) => request('/companies', { method: 'POST', body: JSON.stringify(data) }),
    update: (id, data) => request(`/companies/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id, performed_by) => {
        const qs = performed_by ? `?performed_by=${encodeURIComponent(performed_by)}` : '';
        return request(`/companies/${id}${qs}`, { method: 'DELETE' });
    },
};

/* ── Homepage Landing API ── */
export const homepageAPI = {
    getData: () => request('/homepage/data'),
};

/* ── Admin Panel API (Strictly Backend-Isolated) ── */
function getAdminHeaders(overrideKey) {
    const key = overrideKey || sessionStorage.getItem('samanvaya_admin_key') || 'samanvaya-admin-2026';
    return {
        'X-Admin-Secret': key,
    };
}

export const adminAPI = {
    getProfile: (adminKey) => request('/admin/profile', { headers: getAdminHeaders(adminKey) }),
    getStats: (adminKey) => request('/admin/system-stats', { headers: getAdminHeaders(adminKey) }),
    getCompanies: (adminKey) => request('/admin/companies', { headers: getAdminHeaders(adminKey) }),
    provisionCompany: (data, adminKey) =>
        request('/admin/companies/provision', {
            method: 'POST',
            headers: getAdminHeaders(adminKey),
            body: JSON.stringify(data),
        }),
    reassignLeader: (companyId, data, adminKey) =>
        request(`/admin/companies/${companyId}/assign-leader`, {
            method: 'PUT',
            headers: getAdminHeaders(adminKey),
            body: JSON.stringify(data),
        }),
};
