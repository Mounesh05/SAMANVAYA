export function formatScore(score, decimals = 1) {
  if (score === null || score === undefined) return '—';
  const num = Number(score);
  return isNaN(num) ? String(score) : `${num.toFixed(decimals)}%`;
}

export function formatNumber(num) {
  if (num === null || num === undefined) return '0';
  return Number(num).toLocaleString('en-US');
}

export function getGradeColor(grade) {
  switch (String(grade).toUpperCase()) {
    case 'A':
    case 'A+':
      return '#10b981';
    case 'B':
    case 'B+':
      return '#3b82f6';
    case 'C':
    case 'C+':
      return '#f59e0b';
    case 'D':
    case 'F':
      return '#ef4444';
    default:
      return '#94a3b8';
  }
}

export function getRiskColor(riskLevel) {
  switch (String(riskLevel).toUpperCase()) {
    case 'CRITICAL':
      return '#ef4444';
    case 'HIGH':
      return '#f97316';
    case 'MEDIUM':
      return '#f59e0b';
    case 'LOW':
      return '#10b981';
    default:
      return '#64748b';
  }
}

export function getStatusColor(status) {
  switch (String(status).toLowerCase()) {
    case 'done':
    case 'completed':
    case 'success':
      return '#10b981';
    case 'in_progress':
    case 'running':
      return '#3b82f6';
    case 'review':
    case 'pending':
      return '#a855f7';
    case 'blocked':
    case 'failed':
      return '#ef4444';
    case 'todo':
    default:
      return '#64748b';
  }
}

export function truncate(str, maxLen = 40) {
  if (!str) return '';
  return str.length > maxLen ? `${str.slice(0, maxLen)}...` : str;
}
