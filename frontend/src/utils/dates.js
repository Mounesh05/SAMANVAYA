import { format, formatDistanceToNow, parseISO } from 'date-fns';

/** Format ISO date string to readable date e.g. "Sep 28, 2026" */
export function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    return format(parseISO(dateStr), 'MMM d, yyyy');
  } catch {
    return dateStr;
  }
}

/** Format ISO date string to datetime e.g. "Sep 28, 2026 at 3:08 PM" */
export function formatDateTime(dateStr) {
  if (!dateStr) return '—';
  try {
    return format(parseISO(dateStr), "MMM d, yyyy 'at' h:mm a");
  } catch {
    return dateStr;
  }
}

/** Relative time e.g. "2 hours ago" */
export function timeAgo(dateStr) {
  if (!dateStr) return '—';
  try {
    return formatDistanceToNow(parseISO(dateStr), { addSuffix: true });
  } catch {
    return dateStr;
  }
}
