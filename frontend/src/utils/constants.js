export const ROLES = {
  DEVELOPER: 'DEVELOPER',
  LEAD: 'LEAD',
  PM: 'PM',
  QA: 'QA',
  DEVOPS: 'DEVOPS',
  HR: 'HR',
  CEO: 'CEO',
};

export const ROLE_LABELS = {
  [ROLES.DEVELOPER]: 'Software Engineer',
  [ROLES.LEAD]: 'Tech Lead',
  [ROLES.PM]: 'Product Manager',
  [ROLES.QA]: 'QA Engineer',
  [ROLES.DEVOPS]: 'DevOps Engineer',
  [ROLES.HR]: 'People & Culture (HR)',
  [ROLES.CEO]: 'Executive (CEO)',
};

export const ROLE_COLORS = {
  [ROLES.DEVELOPER]: '#3b82f6',
  [ROLES.LEAD]: '#6366f1',
  [ROLES.PM]: '#06b6d4',
  [ROLES.QA]: '#10b981',
  [ROLES.DEVOPS]: '#f59e0b',
  [ROLES.HR]: '#ec4899',
  [ROLES.CEO]: '#a855f7',
};

export const TASK_STATUS = {
  TODO: 'todo',
  IN_PROGRESS: 'in_progress',
  REVIEW: 'review',
  DONE: 'done',
  BLOCKED: 'blocked',
};

export const STATUS_LABELS = {
  [TASK_STATUS.TODO]: 'To Do',
  [TASK_STATUS.IN_PROGRESS]: 'In Progress',
  [TASK_STATUS.REVIEW]: 'Review',
  [TASK_STATUS.DONE]: 'Done',
  [TASK_STATUS.BLOCKED]: 'Blocked',
};

export const RISK_LEVELS = {
  LOW: 'LOW',
  MEDIUM: 'MEDIUM',
  HIGH: 'HIGH',
  CRITICAL: 'CRITICAL',
};

export const SEVERITY_LEVELS = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical',
};

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export const DEFAULT_ORG_ID = 'ORG001';
