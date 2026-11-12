import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '../tests/mocks/server';
import { performanceApi } from './performance.api';
import { requestError } from '../utils/performanceScoring';

describe('real scoring API error boundary', () => {
  it('treats the real initial-review 404 as an empty review, not a blocked editor', async () => {
    server.use(http.get('*/api/performance/human-reviews/NEW', () => HttpResponse.json({ detail: 'Performance artifact not found' }, { status: 404 })));
    expect(await performanceApi.getHumanReview('NEW')).toBeNull();
  });
  it.each([403, 409])('retains safe HTTP %s metadata without credentials or request bodies', async (status) => {
    server.use(http.get('*/api/performance/readiness', () => HttpResponse.json({ detail: 'Scoped request cannot proceed' }, { status })));
    const error = await performanceApi.getReadiness().catch((e) => e);
    expect(error.response?.status).toBe(status);
    expect(requestError(error)).toMatch(status === 409 ? /draft is preserved/ : /current account cannot access/);
    expect(error).not.toHaveProperty('config');
    expect(error.response).not.toHaveProperty('headers');
  });
});
