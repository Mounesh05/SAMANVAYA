export function qualityStatus(run = {}) {
  if (run.analysis_scope === 'pr_algorithm_intelligence' || run.kind === 'pr_algorithm_intelligence') {
    return 'Algorithm analysis · ' + String(run.status || 'unavailable').replaceAll('_', ' ');
  }
  if (run.status === 'completed' && (run.analysis_scope === 'purpose_discovery' || run.analysis_level === 'purpose_discovery')) {
    return 'Discovery finished · quality not run';
  }
  if (run.quality_analysis_status === 'partial') return 'Partially analyzed';
  return ({pending: 'Queued', running: 'Analyzing', analyzing: 'Analyzing', completed: 'Completed',
    failed: 'Failed', unsupported: 'Unsupported', superseded: 'Superseded',
    insufficient_evidence: 'Insufficient evidence'})[run.status] || 'Status unavailable';
}
