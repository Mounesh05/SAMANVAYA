# Runbook: separate the platform admin from the CEO (CR-008, Decision 1-A)

**New installs (CR-012) are already separated:** first-run setup and
`create_first_user.py` create the Chief Executive without admin rights and a
separate platform administrator (DevOps role). Use this runbook only for
installs set up before CR-012, where the CEO account is also the admin.

Admin rights are for running the platform: accounts, admin rights,
deactivation, teams and projects set-up, and audit logs. They are not needed
for the CEO's executive work, which comes from the CEO role itself.

Do this once, after the platform/IT person has an employee account. Since
CR-010 each step below creates an approval request when a second eligible
admin exists; with the CEO as the only admin, step 2 applies at once and is
audited as "no second approver available".

1. Sign in as the CEO and open **Employees**.
2. On the platform/IT employee's row, choose **Make … an admin** (shield icon).
3. Sign out. Sign in as that employee and check that **Employees** shows the
   shield icons and the Deactivate action.
4. On the CEO's row, choose **Remove admin rights from …**.
5. Check the audit log, then confirm with the CEO that their executive pages
   (Dashboard, Quality, Risk, Organization, Reports) still work.

## Safety rules enforced by the backend

- Only admins can grant or remove admin rights.
- The last active admin can't lose admin rights or be deactivated (HTTP 409).
  Make someone else an admin first.
- Nobody can deactivate their own account or the CEO account.
- Activating or deactivating an account is admin-only, whether it is done with
  Deactivate or through an edit.

## Rolling back

An admin can make the CEO an admin again from the same page.
