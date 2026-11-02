import { ROLES } from './constants';

export function canUpdateTask(user, task) {
  const role = user?.role?.toUpperCase();
  return (
    role === ROLES.PM
    || role === ROLES.LEAD
    || (
      [ROLES.DEVELOPER, ROLES.QA, ROLES.DEVOPS].includes(role)
      && task?.assignee_id === user?.employee_id
    )
  );
}
