import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { FeedbackPage } from './FeedbackPage';
import { RoleGuard } from '../../auth/RoleGuard';
import { performanceApi } from '../../api/performance.api';
import { feedbackApi } from '../../api/feedback.api';
import { useAuthStore } from '../../store/useAuthStore';
import { assignment, mockScoringApi, renderScoring } from '../../test/scoringFixtures';

beforeEach(mockScoringApi);

it.each(['LEAD', 'PM', 'QA', 'DEVOPS', 'HR'])('opens an assigned reviewer inbox for %s', async (role) => {
  renderScoring(<RoleGuard page="feedback"><FeedbackPage /></RoleGuard>, { role, path: '/feedback?target=OTHER' });
  expect(await screen.findByText(/No active assigned reviews/)).toBeVisible();
  expect(screen.queryByLabelText('Target Engineer')).toBeNull();
  expect(screen.queryByRole('button', { name: 'Record observations' })).toBeNull();
  expect(performanceApi.getHumanReview).not.toHaveBeenCalled();
});

it('records the selected assignment and ignores an employee ID in an old bookmark', async () => {
  performanceApi.getAssignments.mockResolvedValue([assignment]);
  renderScoring(<RoleGuard page="feedback"><FeedbackPage /></RoleGuard>, { role: 'LEAD', path: '/feedback?target=OTHER' });
  fireEvent.change(await screen.findByLabelText('Assigned review'), { target: { value: assignment.assignment_id } });
  const note = await screen.findByLabelText('Reason for collaboration');
  fireEvent.click(screen.getByRole('button', { name: 'Record observations' }));
  expect(note).toHaveFocus();
  expect(performanceApi.submitHumanReview).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText('collaboration'), { target: { value: 'UNDER_REVIEW' } });
  fireEvent.change(note, { target: { value: 'The evidence from the handover is awaiting review.' } });
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(screen.getByRole('button', { name: 'Record observations' }));
  expect(await screen.findByText(/Recorded without a score/)).toBeVisible();
  expect(performanceApi.submitHumanReview).toHaveBeenCalledWith(assignment.assignment_id, {
    no_conflict_attested: true, observations: [{ dimension: 'collaboration', state: 'UNDER_REVIEW', rating: null,
      reason: 'The evidence from the handover is awaiting review.', direct_observation: false, evidence: [] }],
  });
});

it('keeps confidential historical cases read-only for the HR author', async () => {
  const lookup = vi.spyOn(feedbackApi, 'getHRAssessment').mockResolvedValue({
    status: 'draft', general_comments: 'Original private note.', dimensions: {
      professional_conduct: { rating: 2, evidence_description: 'Historical log entry.' },
    },
  });
  renderScoring(<FeedbackPage />, { role: 'HR', id: 'H', path: '/feedback' });
  fireEvent.click(screen.getByRole('button', { name: 'Open case history' }));
  const subject = await screen.findByLabelText('Historical case employee');
  expect(lookup).not.toHaveBeenCalled();
  expect([...subject.options].map((option) => option.value)).toEqual(['', 'D', 'Q', 'V', 'L']);
  fireEvent.change(subject, { target: { value: 'D' } });
  expect(await screen.findByText('Historical log entry.')).toBeVisible();
  expect(lookup).toHaveBeenCalledWith('D');
  expect(screen.getByText('Historical rating · 2/4')).toBeVisible();
  expect(screen.getByText('Original private note.')).toBeVisible();
  expect(screen.queryByRole('textbox')).toBeNull();
});

it('provides executive history without offering a numerical review or private HR cases', () => {
  renderScoring(<FeedbackPage />, { role: 'CEO', path: '/feedback' });
  expect(screen.getByRole('link', { name: 'View assessment history' })).toHaveAttribute('href', '/performance/assessments');
  expect(screen.queryByRole('button', { name: 'Open case history' })).toBeNull();
  expect(performanceApi.getAssignments).not.toHaveBeenCalled();
});

it('clears private notes when the same employee changes organizations', async () => {
  performanceApi.getAssignments.mockResolvedValue([assignment]);
  renderScoring(<FeedbackPage />, { id: 'R', path: '/feedback' });
  fireEvent.change(await screen.findByLabelText('Assigned review'), { target: { value: assignment.assignment_id } });
  fireEvent.change(await screen.findByLabelText('Reason for collaboration'), { target: { value: 'Private first-tenant notes.' } });
  act(() => useAuthStore.setState({ user: { ...useAuthStore.getState().user, org_id: 'another' } }));
  await waitFor(() => expect(performanceApi.getAssignments).toHaveBeenCalledTimes(2));
  fireEvent.change(await screen.findByLabelText('Assigned review'), { target: { value: assignment.assignment_id } });
  expect(await screen.findByLabelText('Reason for collaboration')).toHaveValue('');
  expect(performanceApi.getHumanReview).toHaveBeenCalledTimes(2);
});
