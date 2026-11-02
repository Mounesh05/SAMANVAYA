/**
 * Badge variants — Status, Priority, Risk
 */
import { PRIORITY, RISK_LEVELS, TASK_STATUS } from '../../utils/constants';

const STATUS_CLASSES = {
  TODO:        'badge-neutral',
  IN_PROGRESS: 'badge-info',
  REVIEW:      'badge-warning',
  DONE:        'badge-success',
  OPEN:        'badge-neutral',
  ACTIVE:      'badge-info',
  COMPLETED:   'badge-success',
  PLANNED:     'badge-neutral',
  CLOSED:      'badge-neutral',
  PASS:        'badge-success',
  FAIL:        'badge-danger',
  RUNNING:     'badge-info',
  WARNING:     'badge-warning',
};

const PRIORITY_CLASSES = {
  LOW:      'badge-low',
  MEDIUM:   'badge-medium',
  HIGH:     'badge-high',
  CRITICAL: 'badge-critical',
};

const RISK_CLASSES = {
  LOW:      'badge-low',
  MEDIUM:   'badge-medium',
  HIGH:     'badge-high',
  CRITICAL: 'badge-critical',
};

export function StatusBadge({ status }) {
  if (!status) return null;
  const cls = STATUS_CLASSES[status.toUpperCase()] || 'badge-neutral';
  return (
    <span className={`badge ${cls}`}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}

export function PriorityBadge({ priority }) {
  if (!priority) return null;
  const cls = PRIORITY_CLASSES[priority.toUpperCase()] || 'badge-neutral';
  return <span className={`badge ${cls}`}>{priority}</span>;
}

export function RiskBadge({ risk }) {
  if (!risk) return null;
  const cls = RISK_CLASSES[risk.toUpperCase()] || 'badge-neutral';
  return <span className={`badge ${cls}`}>{risk} RISK</span>;
}

export function RoleBadge({ role }) {
  if (!role) return null;
  return <span className="badge badge-brand">{role}</span>;
}
