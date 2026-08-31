import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/common/Button';
import { Home } from 'lucide-react';

export function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div
      style={{
        minHeight: '70vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: '2rem',
      }}
    >
      <h1
        style={{
          fontSize: '5rem',
          fontWeight: '900',
          letterSpacing: '-0.04em',
          background: 'linear-gradient(135deg, #3b82f6 0%, #a855f7 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          marginBottom: '0.5rem',
        }}
      >
        404
      </h1>
      <h2 style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
        Page Not Found
      </h2>
      <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', maxWidth: '420px', marginBottom: '1.5rem' }}>
        The page you are looking for does not exist or you do not have permission to access it.
      </p>
      <Button variant="primary" leftIcon={<Home size={16} />} onClick={() => navigate('/')}>
        Go to Dashboard
      </Button>
    </div>
  );
}
