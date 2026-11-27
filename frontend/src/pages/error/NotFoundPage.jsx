import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/common/Button';
import { Home } from 'lucide-react';

export function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div
      style={{
        maxWidth: '36rem',
        marginBlock: 'clamp(32px, 10vh, 96px)',
      }}
    >
      <p className="font-mono" style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '8px' }}>404</p>
      <h1 style={{ fontSize: '2rem', marginBottom: '8px' }}>Page not found</h1>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '24px' }}>
        The page you are looking for does not exist or you do not have permission to access it.
      </p>
      <Button variant="primary" leftIcon={<Home size={16} />} onClick={() => navigate('/')}>
        Go to dashboard
      </Button>
    </div>
  );
}
