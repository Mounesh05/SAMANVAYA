import { describe, expect, it } from 'vitest';
import { scoringPresentation } from './performanceScoring';

describe('score authority presentation', () => {
  it('preserves historical zero and labels it unverified', () => {
    const result = scoringPresentation({ mode: 'LEGACY_READ_ONLY' }, 0);
    expect(result.score).toBe(0);
    expect(result.label).toMatch(/Legacy/);
    expect(result.approved).toBe(false);
  });
  it('never reuses an old score while a canonical assessment is pending or disputed', () => {
    for (const state of ['DRAFT', 'POLICY_PENDING', 'DISPUTED', 'CANCELLED']) {
      expect(scoringPresentation({ state }, 95).score).toBeNull();
    }
  });
  it('requires an explicit approved number and preserves provisional status', () => {
    expect(scoringPresentation({ state: 'APPROVED' }, 100).approved).toBe(false);
    expect(scoringPresentation({ state: 'APPROVED', approved_score: 85.4 }).approved).toBe(true);
    const pending = scoringPresentation({ state: 'PROVISIONAL', provisional_score: 85.4 });
    expect(pending.score).toBe(85.4);
    expect(pending.label).toMatch(/Provisional/);
  });
  it('rejects nonfinite, string, Boolean and out-of-range score values', () => {
    for (const score of [NaN, Infinity, '85.4', true, -1, 101]) {
      expect(scoringPresentation({ state: 'APPROVED', approved_score: score }).approved).toBe(false);
    }
  });
  it('never promotes an explicitly legacy record with conflicting approval fields', () => {
    expect(scoringPresentation({ mode: 'LEGACY_READ_ONLY', state: 'APPROVED', approved_score: 100 }, 80).approved).toBe(false);
  });
});
