import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from './client';
import { projectsApi } from './projects.api';
import { rolesApi } from './roles.api';

vi.mock('./client', () => ({ default: { get: vi.fn() } }));

beforeEach(() => vi.clearAllMocks());

describe('server-resolved organization requests', () => {
  it.each([
    [() => projectsApi.list(), '/projects/'],
    [() => rolesApi.getExecutionHealth(), '/role/ceo/execution-health'],
    [() => rolesApi.getCriticalRisks(), '/role/ceo/critical-risks'],
    [() => rolesApi.getPMProjects(), '/role/pm/projects'],
  ])('does not invent an organization when none was supplied', async (request, path) => {
    await request();
    expect(apiClient.get).toHaveBeenCalledWith(path, { params: {} });
  });

  it('preserves explicit organization references for server authorization', async () => {
    await projectsApi.list('ORG-EXPLICIT');
    expect(apiClient.get).toHaveBeenCalledWith('/projects/', { params: { org_id: 'ORG-EXPLICIT' } });
  });
});
