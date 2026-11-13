/**
 * CR-012: first-run setup creates a separate Chief Executive and platform
 * administrator. Backend counterparts live in backend/tests/test_first_accounts.py.
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SetupPage } from '../pages/auth/SetupPage';
import { authApi } from '../api/auth.api';

vi.mock('../api/auth.api', () => ({ authApi: { initializeDemoAdmin: vi.fn() } }));

beforeEach(() => vi.clearAllMocks());

async function fill(user, group, values) {
  const box = screen.getByRole('group', { name: group });
  await user.type(within(box).getByLabelText('Email'), values.email);
  await user.type(within(box).getByLabelText('Organisation password'), values.org);
  await user.type(within(box).getByLabelText('Employee password'), values.emp);
}

describe('CR-012 Setup page', () => {
  it('sends both accounts in one request', async () => {
    authApi.initializeDemoAdmin.mockResolvedValue({ available: false });
    render(<MemoryRouter><SetupPage /></MemoryRouter>);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Setup secret'), 'secret');
    await fill(user, /Chief Executive/, { email: 'ceo@samanvaya.com', org: 'Ceo-Org-1!', emp: 'Ceo-Emp-2!' });
    await fill(user, /Platform administrator/, { email: 'it@samanvaya.com', org: 'Adm-Org-3!', emp: 'Adm-Emp-4!' });
    await user.click(screen.getByRole('button', { name: 'Create both accounts' }));
    await waitFor(() => expect(authApi.initializeDemoAdmin).toHaveBeenCalledWith({
      setup_secret: 'secret',
      ceo: { email: 'ceo@samanvaya.com', organisation_password: 'Ceo-Org-1!', employee_password: 'Ceo-Emp-2!' },
      admin: { email: 'it@samanvaya.com', organisation_password: 'Adm-Org-3!', employee_password: 'Adm-Emp-4!' },
    }));
    expect(await screen.findByRole('status')).toHaveTextContent('DEMO-ADMIN');
  });

  it('shows the backend reason when setup is refused', async () => {
    authApi.initializeDemoAdmin.mockRejectedValue({ response: { data: { detail: 'The two accounts must not share a password' } } });
    render(<MemoryRouter><SetupPage /></MemoryRouter>);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Setup secret'), 'secret');
    await fill(user, /Chief Executive/, { email: 'a@samanvaya.com', org: 'x', emp: 'y' });
    await fill(user, /Platform administrator/, { email: 'b@samanvaya.com', org: 'x', emp: 'z' });
    await user.click(screen.getByRole('button', { name: 'Create both accounts' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('must not share a password');
  });
});
