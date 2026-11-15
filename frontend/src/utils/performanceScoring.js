export function validScore(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100;
}

export function scoringPresentation(scoring, legacyScore = null) {
  const rawState = scoring?.state || scoring?.status;
  const state = typeof rawState === 'string' ? rawState : undefined;
  if (scoring?.mode === 'LEGACY_READ_ONLY') {
    return { label: 'Legacy record — unverified methodology', score: validScore(legacyScore) ? legacyScore : null,
      approved: false, legacy: true };
  }
  if (state === 'APPROVED' && validScore(scoring.approved_score)) {
    return { label: 'Approved assessment', score: scoring.approved_score, approved: true, legacy: false };
  }
  if (['PROVISIONAL', 'UNDER_REVIEW'].includes(state)) {
    return { label: 'Provisional — awaiting approval', score: validScore(scoring.provisional_score) ? scoring.provisional_score : null,
      approved: false, legacy: false };
  }
  if (!state && validScore(legacyScore)) {
    return { label: 'Legacy record — unverified methodology', score: validScore(legacyScore) ? legacyScore : null,
      approved: false, legacy: true };
  }
  return { label: state === 'DISPUTED' ? 'Disputed — review pending' : state ? 'Not approved — ' + state.replaceAll('_', ' ').toLowerCase() : 'Not assessed',
    score: null, approved: false, legacy: false };
}

export function requestError(error) {
  if (error?.response?.status === 409) return 'This record changed or is not eligible. Your draft is preserved; reload the latest revision before retrying.';
  if ([401, 403].includes(error?.response?.status)) return 'Your current account cannot access this record. Check your session and project assignment.';
  return typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : 'The request could not be completed. Your draft is preserved; try again.';
}
