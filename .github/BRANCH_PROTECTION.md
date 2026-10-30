# Branch Protection Settings

This document describes the required branch protection rules for the Samanvaya repository to ensure code quality and prevent accidental changes to critical branches.

## Protected Branches

The following branches require protection rules:
- `main` - Production branch
- `testing` - Integration and testing branch

## Required Protection Rules

Configure the following settings for both `main` and `testing` branches:

### 1. Require Pull Request Reviews

- **Setting:** Require pull request reviews before merging
- **Approvals required:** 1
- **Dismiss stale pull request approvals when new commits are pushed:** Enabled (recommended)

### 2. Require Status Checks

- **Setting:** Require status checks to pass before merging
- **Required checks:** 
  - `tests` (from samanvaya-qa.yml workflow)
- **Require branches to be up to date before merging:** Enabled

### 3. Prevent Force Pushes

- **Setting:** Do not allow force pushes
- **Status:** Enabled

### 4. Prevent Branch Deletion

- **Setting:** Do not allow deletions
- **Status:** Enabled

## Setup Instructions

Follow these steps to configure branch protection on GitHub:

1. Navigate to your repository on GitHub
2. Click on **Settings** (requires admin access)
3. In the left sidebar, click **Branches** under "Code and automation"
4. Click **Add branch protection rule**

### For the `main` branch:

5. Enter `main` in the "Branch name pattern" field
6. Enable the following checkboxes:
   - ☑ Require a pull request before merging
     - ☑ Require approvals (set to 1)
     - ☑ Dismiss stale pull request approvals when new commits are pushed
   - ☑ Require status checks to pass before merging
     - ☑ Require branches to be up to date before merging
     - In the search box, type `tests` and select it from the list
   - ☑ Do not allow bypassing the above settings
   - ☑ Restrict who can push to matching branches (if needed)
7. Scroll down and uncheck:
   - ☐ Allow force pushes
   - ☐ Allow deletions
8. Click **Create** to save the rule

### For the `testing` branch:

9. Click **Add branch protection rule** again
10. Enter `testing` in the "Branch name pattern" field
11. Repeat steps 6-8 with the same settings

## Workflow Integration

The branch protection rules rely on the GitHub Actions workflow defined in `.github/workflows/samanvaya-qa.yml`. This workflow:
- Runs on all pushes and pull requests
- Executes the CI script `ci/run_tests.sh`
- Reports test results as a required status check named `tests`

## Verification

After setting up branch protection:

1. Try to push directly to `main` or `testing` - it should be rejected
2. Create a test branch and open a pull request
3. Verify that the PR shows the `tests` status check
4. Verify that the merge button is disabled until:
   - Tests pass
   - At least 1 approval is given
   - The branch is up to date with the base branch

## Notes

- Repository administrators can still bypass these rules if necessary (not recommended)
- These rules ensure that all code changes go through proper review and testing
- If you need to update the required status checks, modify the list in step 6
- For security-sensitive repositories, consider requiring code owners' review and enabling additional checks
