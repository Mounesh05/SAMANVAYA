import React from 'react';
import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { performanceApi } from '../../api/performance.api';
import { AssessmentHistory } from './AssessmentHistory';
import { AssignedObservations } from './AssignedObservations';
import { assignment, mockScoringApi, renderScoring } from '../../test/scoringFixtures';

beforeEach(mockScoringApi);

async function loadEditor(current = null) {
  performanceApi.getAssignments.mockResolvedValue([assignment]);
  performanceApi.getHumanReview.mockResolvedValue(current);
  renderScoring(<AssignedObservations />);
  fireEvent.change(await screen.findByLabelText('Assigned review'), { target: { value: 'AS-1' } });
  return screen.findByLabelText('Reason for collaboration');
}

describe('scoped scoring workflow', () => {
  it('records an explicitly chosen unscored observation without default ratings', async () => {
    const reason = await loadEditor();
    fireEvent.change(screen.getByLabelText('collaboration'), { target: { value: 'NOT_OBSERVED' } });
    fireEvent.change(reason, { target: { value: 'No direct interaction in the assessed period.' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Record observations' }));
    await waitFor(() => expect(performanceApi.submitHumanReview).toHaveBeenCalledTimes(1));
    const [id, body] = performanceApi.submitHumanReview.mock.calls[0];
    expect(id).toBe('AS-1');
    expect(body.observations[0]).toMatchObject({ state: 'NOT_OBSERVED', rating: null, direct_observation: false });
    expect(body).not.toHaveProperty('employee_id');
    expect(await screen.findByText(/Recorded without a score/)).toBeInTheDocument();
  });
  it('requires reasons and explicit conflict attestation', async () => {
    await loadEditor();
    fireEvent.click(screen.getByRole('button', { name: 'Record observations' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Explain every dimension/);
    expect(performanceApi.submitHumanReview).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Reason for collaboration')).toHaveFocus();
  });
  it('keeps notes after a failed save and refuses to silently replace a stale review', async () => {
    const current = { revision: 1, revision_digest: 'a'.repeat(64), observations: [{ dimension: 'collaboration', state: 'NOT_OBSERVED', reason: 'Earlier note.' }] };
    performanceApi.reviseHumanReview.mockRejectedValue({ response: { status: 409 } });
    const reason = await loadEditor(current);
    fireEvent.change(reason, { target: { value: 'My correction remains available after a conflict.' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Record observations' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/draft is preserved/);
    expect(reason).toHaveValue('My correction remains available after a conflict.');
    expect(performanceApi.reviseHumanReview.mock.calls[0][1].expected_digest).toBe('a'.repeat(64));
    expect(performanceApi.submitHumanReview).not.toHaveBeenCalled();
  });
  it('separates current disputed status from an earlier approval and replays only explicit approved revisions', async () => {
    performanceApi.getAssessments.mockResolvedValue([{ assessment_id: 'A1', state: 'DISPUTED', can_appeal: false }]);
    performanceApi.getAssessmentHistory.mockResolvedValue({ current: { state: 'DISPUTED', digest: 'a'.repeat(64) }, history: [
      { event_id: 'E1', revision: 1, state: 'APPROVED', approved_score: 85.4 }, { event_id: 'E2', revision: 2, state: 'DISPUTED', approved_score: null }] });
    renderScoring(<AssessmentHistory employeeId="D" />);
    expect(await screen.findByText('Disputed — review pending')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Replay revision 1' }));
    expect(await screen.findByRole('status')).toHaveTextContent(/reproduced/);
    expect(performanceApi.replayAssessment).toHaveBeenCalledWith('A1', 1);
    expect(screen.queryByRole('button', { name: 'Replay revision 2' })).not.toBeInTheDocument();
  });
  it('preserves a factual challenge on server failure and uses the original expected revision', async () => {
    performanceApi.getAssessments.mockResolvedValue([{ assessment_id: 'A1', state: 'DRAFT', can_appeal: true }]);
    performanceApi.getAssessmentHistory.mockResolvedValue({ current: { state: 'DRAFT', digest: 'a'.repeat(64) }, history: [] });
    performanceApi.appealAssessment.mockRejectedValue({ response: { status: 409 } });
    renderScoring(<AssessmentHistory employeeId="D" />, { role: 'DEVELOPER', id: 'D' });
    const field = await screen.findByLabelText('Factual challenge');
    fireEvent.change(field, { target: { value: 'The source belongs to another period.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record factual challenge' }));
    await waitFor(() => expect(performanceApi.appealAssessment).toHaveBeenCalled());
    expect(field).toHaveValue('The source belongs to another period.');
    expect(performanceApi.appealAssessment.mock.calls[0][1].expected_digest).toBe('a'.repeat(64));
    expect(screen.getByRole('button', { name: 'Reload latest assessment' })).toBeInTheDocument();
    performanceApi.getAssessmentHistory.mockResolvedValue({ current: { state: 'DISPUTED', revision: 2, digest: 'b'.repeat(64) }, history: [] });
    fireEvent.click(screen.getByRole('button', { name: 'Reload latest assessment' }));
    const adopt = await screen.findByRole('button', { name: 'Use latest assessment after review' });
    expect(screen.getByLabelText('Factual challenge')).toHaveValue('The source belongs to another period.');
    expect(performanceApi.appealAssessment).toHaveBeenCalledTimes(1);
    fireEvent.click(adopt);
    fireEvent.click(screen.getByRole('button', { name: 'Record factual challenge' }));
    await waitFor(() => expect(performanceApi.appealAssessment).toHaveBeenCalledTimes(2));
    expect(performanceApi.appealAssessment.mock.calls[1][1]).toMatchObject({ expected_digest: 'b'.repeat(64), reason: 'The source belongs to another period.' });
    expect(performanceApi.appealAssessment.mock.calls[1][1].request_id).not.toBe(performanceApi.appealAssessment.mock.calls[0][1].request_id);
  });

  it('preserves newer challenge notes when an earlier appeal finishes after switching assessments', async () => {
    let finish;
    performanceApi.getAssessments.mockResolvedValue(['A1', 'A2'].map((assessment_id) => ({ assessment_id, state: 'DRAFT', can_appeal: true })));
    performanceApi.getAssessmentHistory.mockResolvedValue({ current: { state: 'DRAFT', digest: 'a'.repeat(64) }, history: [] });
    performanceApi.appealAssessment.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    renderScoring(<AssessmentHistory employeeId="D" />, { role: 'DEVELOPER', id: 'D' });
    fireEvent.change(await screen.findByLabelText('Factual challenge'), { target: { value: 'First submitted challenge.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record factual challenge' }));
    await waitFor(() => expect(performanceApi.appealAssessment).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('Assessment'), { target: { value: 'A2' } });
    await screen.findByLabelText('Factual challenge');
    fireEvent.change(screen.getByLabelText('Assessment'), { target: { value: 'A1' } });
    fireEvent.change(await screen.findByLabelText('Factual challenge'), { target: { value: 'Newer factual notes must remain.' } });
    finish({ state: 'DISPUTED' });
    await screen.findByText(/Challenge recorded/);
    fireEvent.change(screen.getByLabelText('Assessment'), { target: { value: 'A2' } });
    await screen.findByLabelText('Factual challenge');
    fireEvent.change(screen.getByLabelText('Assessment'), { target: { value: 'A1' } });
    expect(await screen.findByLabelText('Factual challenge')).toHaveValue('Newer factual notes must remain.');
  });

  it('never lets a late save delete a newer draft after switching away and back', async () => {
    let finish;
    performanceApi.submitHumanReview.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    const reason = await loadEditor();
    fireEvent.change(screen.getByLabelText('collaboration'), { target: { value: 'NOT_OBSERVED' } });
    fireEvent.change(reason, { target: { value: 'Earlier submitted draft.' } });
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Record observations' }));
    await waitFor(() => expect(performanceApi.submitHumanReview).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('Assigned review'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Assigned review'), { target: { value: 'AS-1' } });
    const newer = await screen.findByLabelText('Reason for collaboration');
    fireEvent.change(newer, { target: { value: 'Newer notes that must survive an earlier response.' } });
    finish({ status: 'RECORDED_UNVERIFIED' });
    await screen.findByText(/Recorded without a score/);
    fireEvent.change(screen.getByLabelText('Assigned review'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Assigned review'), { target: { value: 'AS-1' } });
    await screen.findByLabelText('Reason for collaboration');
    await waitFor(() => expect(screen.getByLabelText('Reason for collaboration')).toHaveValue('Newer notes that must survive an earlier response.'));
    expect(screen.getByRole('button', { name: 'Discard draft' })).toBeInTheDocument();
  });
});
