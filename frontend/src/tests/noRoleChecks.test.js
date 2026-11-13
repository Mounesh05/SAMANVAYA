/**
 * Guard: the frontend decides what someone can do from the permissions the
 * backend sends (/api/auth/me), never from their role name.
 *
 * This fails when a source file compares the signed-in user's role, for
 * example `role === ROLES.PM`, `['LEAD', 'PM'].includes(role)` or
 * `switch (role)`. Use hasPermission / hasAnyPermission / canOpenPage instead.
 *
 * Allowed on purpose:
 * - routes/access.js: role dashboards are persona views keyed by role, and a
 *   few pages still list roles there (one table, reviewed per change request);
 * - the Sidebar's dashboard link, which opens the user's own role dashboard.
 * Comparisons on an employee record (`e.role`, `employee.role`) are about the
 * record, not the viewer, and are not matched.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import { describe, expect, it } from 'vitest';

const SRC = resolve(process.cwd(), 'src');  // vitest runs from the frontend folder
const VIEWER_ROLE_CHECK = /(?<![.\w])(role|roleUpper|userRole)\s*(===|!==)|\.includes\((role|roleUpper|userRole)\)|switch\s*\((role|roleUpper|userRole)\)|\w+\[(role|roleUpper)\]\)?\s*(\|\||\?\.)\s*\{\}/;
const ALLOWED = new Map([
  ['routes/access.js', () => true],
  ['components/layout/Sidebar.jsx', (line) => line.includes('knownRole')],
]);

function sourceFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) return name === 'tests' ? [] : sourceFiles(full);
    return /\.(js|jsx)$/.test(name) && !/\.(test|stress\.test)\.(js|jsx)$/.test(name) ? [full] : [];
  });
}

describe('frontend access decisions use permissions', () => {
  it('has no role-name checks on the signed-in user', () => {
    const offenders = [];
    for (const file of sourceFiles(SRC)) {
      const rel = relative(SRC, file).split(sep).join('/');
      readFileSync(file, 'utf8').split('\n').forEach((line, index) => {
        if (!VIEWER_ROLE_CHECK.test(line)) return;
        const allowed = ALLOWED.get(rel);
        if (allowed && allowed(line)) return;
        offenders.push(`${rel}:${index + 1}: ${line.trim()}`);
      });
    }
    expect(offenders, `Use permissions instead of role names:\n${offenders.join('\n')}`).toEqual([]);
  });
});
