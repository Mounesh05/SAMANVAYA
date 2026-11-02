import { describe, expect, it } from 'vitest';
import { canUpdateTask } from '../../utils/taskPermissions';

describe('canUpdateTask', () => {
  const task = { assignee_id: 'DEMO-MOUNESH' };

  it('allows a developer to update only their own task', () => {
    expect(
      canUpdateTask({ role: 'DEVELOPER', employee_id: 'DEMO-MOUNESH' }, task),
    ).toBe(true);
    expect(
      canUpdateTask({ role: 'DEVELOPER', employee_id: 'DEMO-SUMITH' }, task),
    ).toBe(false);
  });

  it('allows project managers and leads to update project tasks', () => {
    expect(canUpdateTask({ role: 'PM' }, task)).toBe(true);
    expect(canUpdateTask({ role: 'LEAD' }, task)).toBe(true);
  });

  it('allows QA and DevOps to update only tasks assigned to them', () => {
    for (const role of ['QA', 'DEVOPS']) {
      expect(canUpdateTask({ role, employee_id: 'DEMO-MOUNESH' }, task)).toBe(true);
      expect(canUpdateTask({ role, employee_id: 'DEMO-SUMITH' }, task)).toBe(false);
    }
  });

  it('does not grant backlog write access to administrative or unrelated roles', () => {
    expect(canUpdateTask({ role: 'HR', employee_id: 'DEMO-MOUNESH' }, task)).toBe(false);
    expect(canUpdateTask({ role: 'CEO', employee_id: 'DEMO-MOUNESH' }, task)).toBe(false);
  });
});
