import { hasPermission, PERMISSIONS } from '../auth/permissions';

// CR-002: QA sign-off. Work waiting in Review can be passed (done) or failed
// (back to in_progress). Mirrors core/authorization.py on the backend.
export const SIGN_OFF_FROM = 'review';
export const SIGN_OFF_TARGETS = Object.freeze(['done', 'in_progress']);

// Same rule as verify_task_status_update_access on the backend:
// MOVE_TASK (PM, Lead) moves any task; TRANSITION_TASK moves your own tasks.
function canMoveAnyTask(user) {
  return hasPermission(user, PERMISSIONS.MOVE_TASK);
}

function isAssignedEngineer(user, task) {
  return !canMoveAnyTask(user)
    && hasPermission(user, PERMISSIONS.TRANSITION_TASK)
    && task?.assignee_id === user?.employee_id;
}

/** True when the user may move this task only as a QA sign-off. */
export function isSignOffOnly(user, task) {
  return !canMoveAnyTask(user)
    && !isAssignedEngineer(user, task)
    && task?.status === SIGN_OFF_FROM
    && hasPermission(user, PERMISSIONS.SIGN_OFF_WORK);
}

export function canUpdateTask(user, task) {
  return canMoveAnyTask(user) || isAssignedEngineer(user, task) || isSignOffOnly(user, task);
}
