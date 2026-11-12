import { ROLES } from './constants';
import { hasPermission, PERMISSIONS } from '../auth/permissions';

// CR-002: QA sign-off. Work waiting in Review can be passed (done) or failed
// (back to in_progress). Mirrors core/authorization.py on the backend.
export const SIGN_OFF_FROM = 'review';
export const SIGN_OFF_TARGETS = Object.freeze(['done', 'in_progress']);

function isAssignedEngineer(user, task) {
  const role = user?.role?.toUpperCase();
  return [ROLES.DEVELOPER, ROLES.QA, ROLES.DEVOPS].includes(role)
    && task?.assignee_id === user?.employee_id;
}

/** True when the user may move this task only as a QA sign-off. */
export function isSignOffOnly(user, task) {
  return !isAssignedEngineer(user, task)
    && task?.status === SIGN_OFF_FROM
    && hasPermission(user, PERMISSIONS.SIGN_OFF_WORK);
}

export function canUpdateTask(user, task) {
  const role = user?.role?.toUpperCase();
  return (
    role === ROLES.PM
    || role === ROLES.LEAD
    || isAssignedEngineer(user, task)
    || isSignOffOnly(user, task)
  );
}
