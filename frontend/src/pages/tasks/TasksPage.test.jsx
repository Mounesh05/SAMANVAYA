import { withPermissions } from '../../tests/utils/roleUser';
import { describe, expect, it } from 'vitest';
import { canUpdateTask } from '../../utils/taskPermissions';

describe('canUpdateTask', () => {
  const task = { assignee_id: 'DEMO-MOUNESH' };

  it('allows a developer to update only their own task', () => {
    expect(
      canUpdateTask(withPermissions({ role: 'DEVELOPER', employee_id: 'DEMO-MOUNESH' }), task),
    ).toBe(true);
    expect(
      canUpdateTask(withPermissions({ role: 'DEVELOPER', employee_id: 'DEMO-SUMITH' }), task),
    ).toBe(false);
  });

  it('allows project managers and leads to update project tasks', () => {
    expect(canUpdateTask(withPermissions({ role: 'PM' }), task)).toBe(true);
    expect(canUpdateTask(withPermissions({ role: 'LEAD' }), task)).toBe(true);
  });

  it('allows QA and DevOps to update only tasks assigned to them', () => {
    for (const role of ['QA', 'DEVOPS']) {
      expect(canUpdateTask(withPermissions({ role, employee_id: 'DEMO-MOUNESH' }), task)).toBe(true);
      expect(canUpdateTask(withPermissions({ role, employee_id: 'DEMO-SUMITH' }), task)).toBe(false);
    }
  });

  it('does not grant backlog write access to administrative or unrelated roles', () => {
    expect(canUpdateTask(withPermissions({ role: 'HR', employee_id: 'DEMO-MOUNESH' }), task)).toBe(false);
    expect(canUpdateTask(withPermissions({ role: 'CEO', employee_id: 'DEMO-MOUNESH' }), task)).toBe(false);
  });
});
