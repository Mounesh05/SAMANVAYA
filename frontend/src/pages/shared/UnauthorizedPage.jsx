import { Link } from 'react-router-dom';
import { ShieldOff } from 'lucide-react';
import { usePermissions } from '../../hooks/usePermissions';

export function UnauthorizedPage() {
  const { dashboardPath } = usePermissions();
  return (
    <div className="state-container" style={{ minHeight: '80vh' }}>
      <div className="state-icon" style={{ background: 'var(--danger-bg)', color: 'var(--danger)', width: 64, height: 64 }}>
        <ShieldOff size={32} aria-hidden="true" />
      </div>
      <h1 className="state-title" style={{ fontSize: '1.25rem' }}>Access Denied</h1>
      <p className="state-description">You do not have permission to access this page.</p>
      <Link to={dashboardPath} className="btn btn-primary">Return to Dashboard</Link>
    </div>
  );
}

export function NotFoundPage() {
  return (
    <div className="state-container" style={{ minHeight: '100vh' }}>
      <div style={{ fontSize: '4rem', fontWeight: 800, color: 'var(--brand-500)', letterSpacing: '-0.04em', lineHeight: 1 }}>404</div>
      <h1 className="state-title" style={{ fontSize: '1.25rem' }}>Page Not Found</h1>
      <p className="state-description">The page you're looking for doesn't exist or has been moved.</p>
      <Link to="/" className="btn btn-primary">Go Home</Link>
    </div>
  );
}
