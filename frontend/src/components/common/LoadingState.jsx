import React from 'react';
import { Loader2 } from 'lucide-react';

export function LoadingState({ message = 'Loading data...', minHeight = '240px' }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight,
        gap: '0.75rem',
      }}
    >
      <Loader2 size={32} className="animate-spin" style={{ color: 'var(--primary)' }} />
      <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)', fontWeight: '500' }}>
        {message}
      </span>
    </div>
  );
}
