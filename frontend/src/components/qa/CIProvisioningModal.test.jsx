import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { CIProvisioningModal } from './CIProvisioningModal';

describe('CIProvisioningModal', () => {
  it('sends only the branch and closes when CI is enabled', async () => {
    const onProvision = vi.fn().mockResolvedValue({ status: 'provisioned' });
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<CIProvisioningModal isOpen projectId="PRJ-1" onProvision={onProvision} onClose={onClose} />);

    const branch = screen.getByLabelText('Branch');
    await user.clear(branch);
    await user.type(branch, 'release/2026.11');
    await user.click(screen.getByRole('button', { name: 'Enable CI' }));

    await waitFor(() => expect(onProvision).toHaveBeenCalledWith({ branch: 'release/2026.11' }));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows the backend explanation and stays open when enabling fails', async () => {
    const onProvision = vi.fn().mockRejectedValue(
      new Error('Link this project to its GitHub repository (GitHub Sync settings) before enabling CI'),
    );
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<CIProvisioningModal isOpen projectId="PRJ-1" onProvision={onProvision} onClose={onClose} />);

    await user.click(screen.getByRole('button', { name: 'Enable CI' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('GitHub Sync settings');
    expect(onClose).not.toHaveBeenCalled();
  });

  it('rejects an unsafe branch name before calling the server', async () => {
    const onProvision = vi.fn();
    const user = userEvent.setup();
    render(<CIProvisioningModal isOpen projectId="PRJ-1" onProvision={onProvision} onClose={() => {}} />);

    const branch = screen.getByLabelText('Branch');
    await user.clear(branch);
    await user.type(branch, 'a..b');
    await user.click(screen.getByRole('button', { name: 'Enable CI' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('no ".."');
    expect(onProvision).not.toHaveBeenCalled();
  });
});
