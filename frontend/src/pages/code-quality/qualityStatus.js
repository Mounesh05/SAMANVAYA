export function isQualityActive(run) {
  return ['pending', 'running', 'analyzing'].includes(run?.status);
}

export function qualityTone(run) {
  if (run?.status === 'failed') return 'danger';
  if (isQualityActive(run)) return 'active';
  if (run?.quality_analysis_status === 'partial' || run?.is_truncated) return 'warning';
  if (run?.quality_analysis_status === 'available' && run.status === 'completed') return 'success';
  return 'neutral';
}

export function fileScopeLabel(run = {}) {
  if (run.kind === 'pr_algorithm_intelligence' || run.analysis_scope === 'pr_algorithm_intelligence') return 'Algorithm';
  if (run.kind === 'pr_quality_comparison' || run.file_scope === 'pr_comparison') return 'PR comparison';
  if (run.file_scope === 'pr_changes' || run.kind?.startsWith('pr_quality_')) return 'PR changed files';
  if (run.file_scope === 'repository') return 'Whole revision';
  return Array.isArray(run.changed_files) || run.file_scope === 'selected_files' ? 'Selected files' : 'Unrecorded';
}

export function hasFullFileCount(count) {
  return count?.selected > 0 && count.analyzed === count.selected;
}

export function qualityStatus(run = {}) {
  if (run.analysis_scope === 'pr_algorithm_intelligence' || run.kind === 'pr_algorithm_intelligence') {
    return 'Algorithm analysis · ' + String(run.status || 'unavailable').replaceAll('_', ' ');
  }
  if (run.status === 'completed' && (run.analysis_scope === 'purpose_discovery' || run.analysis_level === 'purpose_discovery')) {
    return 'Discovery finished · quality not run';
  }
  if (run.status === 'completed' && run.is_truncated) {
    return 'Truncated (partial scope)';
  }
  if (run.status === 'completed' && run.quality_analysis_status === 'partial') {
    const fileCounts = run.file_counts;
    const allFiles = fileCounts
      ? ['base', 'head'].every(side => hasFullFileCount(fileCounts[side])) && !run.quality_unavailable_reason
      : hasFullFileCount({ selected: run.source_selection_count, analyzed: run.files_analyzed });
    return allFiles ? 'Analyzed with measurement gaps' : 'Partially analyzed';
  }
  return ({pending: 'Queued', running: 'Analyzing', analyzing: 'Analyzing', completed: 'Completed',
    failed: 'Failed', unsupported: 'Unsupported', superseded: 'Superseded',
    insufficient_evidence: 'Insufficient evidence'})[run.status] || 'Status unavailable';
}
