import apiClient from './client';
import { DEFAULT_ORG_ID } from '../utils/constants';

export const rolesApi = {
  // Developer
  getDeveloperDashboard: async () => {
    return apiClient.get('/role/developer/dashboard');
  },
  getMyTasks: async () => {
    return apiClient.get('/role/developer/my-tasks');
  },
  getMyPRs: async () => {
    return apiClient.get('/role/developer/my-prs');
  },

  // Lead
  getLeadDashboard: async () => {
    return apiClient.get('/role/lead/dashboard');
  },
  getTeamOverview: async () => {
    return apiClient.get('/role/lead/team');
  },
  getReviewQueue: async () => {
    return apiClient.get('/role/lead/review-queue');
  },

  // PM
  getPMDashboard: async () => {
    return apiClient.get('/role/pm/dashboard');
  },
  getPMProjects: async (orgId = DEFAULT_ORG_ID) => {
    return apiClient.get('/role/pm/projects', { params: { org_id: orgId } });
  },
  getProjectHealth: async (projectId) => {
    return apiClient.get(`/role/pm/project/${projectId}/health`);
  },
  getPMRisks: async () => {
    return apiClient.get('/role/pm/risks');
  },

  // CEO
  getCEODashboard: async () => {
    return apiClient.get('/role/ceo/dashboard');
  },
  getExecutionHealth: async (orgId = DEFAULT_ORG_ID) => {
    return apiClient.get('/role/ceo/execution-health', { params: { org_id: orgId } });
  },
  getCriticalRisks: async (orgId = DEFAULT_ORG_ID) => {
    return apiClient.get('/role/ceo/critical-risks', { params: { org_id: orgId } });
  },

  // HR
  getHRDashboard: async () => {
    return apiClient.get('/role/hr/dashboard');
  },
  getHREmployees: async () => {
    return apiClient.get('/role/hr/employees');
  },
  getTeamCapacity: async () => {
    return apiClient.get('/role/hr/capacity');
  },

  // QA
  getQADashboard: async () => {
    return apiClient.get('/role/qa/dashboard');
  },
  getTestHealth: async () => {
    return apiClient.get('/role/qa/test-health');
  },
  getBugs: async () => {
    return apiClient.get('/role/qa/bugs');
  },

  // DevOps
  getDevOpsDashboard: async () => {
    return apiClient.get('/role/devops/dashboard');
  },
  getPipelines: async () => {
    return apiClient.get('/role/devops/pipelines');
  },
  getDeployments: async () => {
    return apiClient.get('/role/devops/deployments');
  },
};
