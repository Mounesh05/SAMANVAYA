import React, { useState } from 'react';
import { Modal } from '../common/Modal';
import { Input } from '../common/Input';
import { Button } from '../common/Button';

// Same rule as the backend (domain/models/qa_ci_config.py).
const BRANCH_PATTERN = /^[A-Za-z0-9._/-]{1,200}$/;

function branchError(branch) {
  if (!branch.trim()) return 'Enter a branch name.';
  if (!BRANCH_PATTERN.test(branch) || branch.startsWith('-') || branch.includes('..')) {
    return 'Use letters, numbers, ".", "_", "-" or "/" (no spaces, no "..").';
  }
  return '';
}

/**
 * Enable CI test automation for one branch of the project's linked GitHub
 * repository. The backend always uses the repository linked to the project.
 */
export function CIProvisioningModal({ isOpen, onClose, onProvision, projectId }) {
  const [branch, setBranch] = useState('main');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const close = () => {
    setError('');
    setIsSubmitting(false);
    onClose?.();
  };

  const submit = async (event) => {
    event?.preventDefault();
    const problem = branchError(branch);
    if (problem) {
      setError(problem);
      return;
    }
    setError('');
    setIsSubmitting(true);
    try {
      await onProvision?.({ branch: branch.trim() });
      setBranch('main');
      close();
    } catch (failure) {
      setError(failure?.message || 'CI could not be enabled.');
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={close}
      title="Enable CI Test Automation"
      subtitle={`Adds a GitHub Actions workflow to the repository linked to project ${projectId || ''}. Every push and pull request will run the tests and report results here.`}
      footer={
        <>
          <Button variant="secondary" onClick={close} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} isLoading={isSubmitting}>
            Enable CI
          </Button>
        </>
      }
    >
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <Input
          id="ci-branch"
          label="Branch"
          value={branch}
          onChange={(event) => { setBranch(event.target.value); setError(''); }}
          placeholder="main"
          disabled={isSubmitting}
        />
        <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', margin: 0 }}>
          The repository comes from this project's GitHub Sync settings. The workflow and its secrets are written with the server's GitHub token.
        </p>
        {error && (
          <p role="alert" style={{ fontSize: '0.875rem', color: 'var(--danger)', margin: 0 }}>
            {error}
          </p>
        )}
      </form>
    </Modal>
  );
}
