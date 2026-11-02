/**
 * LoadingState, EmptyState, ErrorState — standardised UI states
 */
import { AlertCircle, InboxIcon, RefreshCw } from 'lucide-react';

export function LoadingState({ message = 'Loading...' }) {
  return (
    <div className="state-container" role="status" aria-live="polite">
      <div className="spinner spinner-lg" aria-hidden="true" />
      <p className="state-description">{message}</p>
    </div>
  );
}

export function EmptyState({ title = 'Nothing here yet', description, action }) {
  return (
    <div className="state-container">
      <div className="state-icon">
        <InboxIcon size={28} aria-hidden="true" />
      </div>
      <p className="state-title">{title}</p>
      {description && <p className="state-description">{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ title = 'Something went wrong', description, onRetry }) {
  return (
    <div className="state-container">
      <div className="state-icon" style={{ background: 'var(--danger-bg)', color: 'var(--danger)' }}>
        <AlertCircle size={28} aria-hidden="true" />
      </div>
      <p className="state-title">{title}</p>
      {description && (
        <p className="state-description">{description}</p>
      )}
      {onRetry && (
        <button className="btn btn-secondary btn-sm" onClick={onRetry}>
          <RefreshCw size={14} />
          Retry
        </button>
      )}
    </div>
  );
}
