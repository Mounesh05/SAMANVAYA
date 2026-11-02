/* ── Role Hierarchy ──
 * Centralized source of truth for the organizational hierarchy.
 *
 * Hierarchy (top → bottom):
 *   CEO  →  can assign to everyone below
 *   HR   →  can assign to everyone except CEO
 *   PM   →  can assign to LEAD, DEVELOPER, DEVOPS, QA
 *   LEAD →  can assign to DEVELOPER, DEVOPS, QA (department team members)
 *   DEVELOPER, DEVOPS, QA  →  cannot assign tasks
 */

/* Ordered from highest authority to lowest */
export const ROLE_HIERARCHY = ['CEO', 'HR', 'PM', 'LEAD', 'DEVELOPER', 'DEVOPS', 'QA'];

/* Explicit mapping: which roles each role can assign tasks to */
export const ROLE_CAN_ASSIGN_TO = {
    CEO: ['HR', 'PM', 'LEAD', 'DEVELOPER', 'DEVOPS', 'QA'],
    HR: ['PM', 'LEAD', 'DEVELOPER', 'DEVOPS', 'QA'],
    PM: ['LEAD', 'DEVELOPER', 'DEVOPS', 'QA'],
    LEAD: ['DEVELOPER', 'DEVOPS', 'QA'],
    DEVELOPER: [],
    DEVOPS: [],
    QA: [],
};

/* Display names for each role */
export const ROLE_DISPLAY_NAMES = {
    CEO: 'CEO',
    HR: 'HR Manager',
    PM: 'Project Manager',
    LEAD: 'Scrum Master',
    DEVELOPER: 'Developer',
    DEVOPS: 'DevOps Engineer',
    QA: 'QA Engineer',
};

/**
 * Given the current user's role, filter an array of employee objects
 * to only those whose role is below the current user in the hierarchy.
 *
 * @param {string} currentRole  – The logged-in user's role key (e.g. 'PM')
 * @param {Array}  employeeList – Array of objects that each have a `role` property.
 *                                The `role` can be either the role key ('DEVELOPER')
 *                                or a display name ('Developer'). Both are handled.
 * @returns {Array} – Filtered employees the current role can assign to
 */
export function getAssignableMembers(currentRole, employeeList) {
    const allowedRoles = ROLE_CAN_ASSIGN_TO[currentRole] || [];

    /* Build a set of allowed role keys AND their display names for flexible matching */
    const allowedSet = new Set();
    allowedRoles.forEach(r => {
        allowedSet.add(r);
        if (ROLE_DISPLAY_NAMES[r]) allowedSet.add(ROLE_DISPLAY_NAMES[r]);
    });

    return employeeList.filter(emp => {
        const empRole = emp.role || '';
        return allowedSet.has(empRole);
    });
}

/**
 * Check whether a given role can assign tasks at all.
 */
export function canRoleAssign(role) {
    return (ROLE_CAN_ASSIGN_TO[role] || []).length > 0;
}
