import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../tests/utils/test-utils';
import { ReleaseGateSettings } from './ReleaseGateSettings';
import apiClient from '../../api/client';

vi.mock('../../api/client', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

it('displays the issued token once and revokes against the observed version', async () => {
  const base = { repository: null, linked_repository: 'pilot/service', enabled: false, version: 0 };
  const issued = { ...base, repository: base.linked_repository, enabled: true, version: 1 };
  apiClient.get.mockResolvedValueOnce(base).mockResolvedValueOnce(issued)
    .mockResolvedValue({ ...issued, version: 2, enabled: false });
  apiClient.post.mockResolvedValueOnce({ ...issued, token: 'fixture-credential' }).mockResolvedValueOnce({});
  renderWithProviders(<ReleaseGateSettings projectId="P" />);
  fireEvent.click(await screen.findByRole('button', { name: 'Issue credential' }));
  expect(await screen.findByLabelText('One-time release gate token')).toHaveValue('fixture-credential');
  expect(apiClient.post).toHaveBeenCalledWith('/projects/P/release-gate',
    { action: 'issue', version: 0, repository: 'pilot/service' });
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss token' }));
  expect(screen.queryByDisplayValue('fixture-credential')).toBeNull();
  const keyboard = userEvent.setup();
  const revoke = screen.getByRole('button', { name: 'Revoke credential' });
  await keyboard.click(revoke);
  expect(apiClient.post).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus();
  await keyboard.tab({ shift: true });
  expect(screen.getByRole('button', { name: 'Revoke', exact: true })).toHaveFocus();
  await keyboard.keyboard('{Escape}');
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(revoke).toHaveFocus();
  fireEvent.click(screen.getByRole('button', { name: 'Revoke credential' }));
  fireEvent.click(screen.getByRole('button', { name: 'Revoke', exact: true }));
  await waitFor(() => expect(apiClient.post).toHaveBeenLastCalledWith('/projects/P/release-gate',
    { action: 'revoke', version: 1, repository: 'pilot/service' }));
  expect(await screen.findByRole('button', { name: 'Issue credential' })).toBeEnabled();
});
