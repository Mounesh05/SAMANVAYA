import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { StoriesPage } from './StoriesPage';
import { projectsApi } from '../../api/projects.api';
import { sprintsApi } from '../../api/sprints.api';
import { storiesApi } from '../../api/stories.api';
import { employeesApi } from '../../api/employees.api';

vi.mock('../../api/projects.api', () => ({
  projectsApi: { list: vi.fn() },
}));
vi.mock('../../api/sprints.api', () => ({
  sprintsApi: { listByProject: vi.fn() },
}));
vi.mock('../../api/stories.api', () => ({
  storiesApi: { listBySprint: vi.fn() },
}));
vi.mock('../../api/employees.api', () => ({
  employeesApi: { list: vi.fn() },
}));

describe('StoriesPage', () => {
  beforeEach(() => {
    projectsApi.list.mockResolvedValue([{ id: 'PRJ-1', name: 'CampusConnect' }]);
    sprintsApi.listByProject.mockResolvedValue([{ id: 'SPR-1', name: 'Sprint 1' }]);
    storiesApi.listBySprint.mockResolvedValue([]);
    employeesApi.list.mockResolvedValue([]);
  });

  it('loads sprint options and stories for the default project automatically', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <StoriesPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(sprintsApi.listByProject).toHaveBeenCalledWith('PRJ-1');
    });
    await waitFor(() => {
      expect(storiesApi.listBySprint).toHaveBeenCalledWith('SPR-1');
    });
    expect(await screen.findByRole('option', { name: 'Sprint 1' })).toBeInTheDocument();
  });
});
