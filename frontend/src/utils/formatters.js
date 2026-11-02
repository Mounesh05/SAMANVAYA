/** Convert score number to color class */
export function scoreColor(score) {
  if (score >= 80) return 'text-green';
  if (score >= 60) return 'text-yellow';
  return 'text-red';
}

/** Capitalize first letter */
export function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

/** Format a percentage e.g. 87 → "87%" */
export function formatPercent(value) {
  if (value === null || value === undefined) return '—';
  return `${Math.round(value)}%`;
}

/** Truncate long text */
export function truncate(str, maxLen = 60) {
  if (!str) return '';
  return str.length > maxLen ? str.slice(0, maxLen) + '…' : str;
}

/** Convert snake_case or UPPER_SNAKE to Title Case */
export function titleCase(str) {
  if (!str) return '';
  return str
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Get initials from a name e.g. "Alice Smith" → "AS" */
export function initials(name) {
  if (!name) return '?';
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}
