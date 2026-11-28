/**
 * Algorithm Intelligence visibility follows USE_ENGINEERING_INTELLIGENCE, the
 * same permission the backend algorithm routes check (api/routes/algorithms.py).
 */
import { describe, expect, it } from 'vitest';
import { canOpenPage, showInMenu } from '../routes/access';
import { ROLES } from '../utils/constants';
import { roleUser } from './utils/roleUser';

describe('Algorithm Intelligence access', () => {
  it.each([
    [ROLES.DEVELOPER, false, true],
    [ROLES.LEAD, false, true],
    [ROLES.QA, false, true],
    [ROLES.DEVOPS, false, true],
    [ROLES.PM, false, true],
    [ROLES.CEO, true, true], // an authorized (admin) CEO
    [ROLES.CEO, false, false],
    [ROLES.HR, false, false],
  ])('%s (admin %s) can open and see it: %s', (role, isAdmin, allowed) => {
    const user = roleUser(role, { is_admin: isAdmin });
    expect(canOpenPage(user, 'algorithmIntelligence')).toBe(allowed);
    expect(showInMenu(user, 'algorithmIntelligence')).toBe(allowed);
  });

  it('does not depend on the Code Quality permission', () => {
    const pm = roleUser(ROLES.PM);
    expect(canOpenPage(pm, 'codeQuality')).toBe(false);
    expect(canOpenPage(pm, 'algorithmIntelligence')).toBe(true);
  });
});
