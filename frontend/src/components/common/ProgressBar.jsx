import React from 'react';

export function ProgressBar({
  value = 0,
  max = 100,
  color = 'primary', // 'primary' | 'success' | 'warning' | 'danger' | 'cyan' | 'purple'
  showLabel = false,
  height = '8px',
  className = '',
}) {
  const percentage = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;

  const colorStyles = {
    primary: 'var(--primary)',
    success: 'var(--success)',
    warning: 'var(--warning)',
    danger: 'var(--danger)',
    cyan: 'var(--cyan)',
    purple: 'var(--purple)',
  };

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '0.25rem' }} className={className}>
      {showLabel && (
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-muted)' }}>
          <span>Progress</span>
          <span>{percentage.toFixed(0)}%</span>
        </div>
      )}
      <div
        style={{
          width: '100%',
          height,
          backgroundColor: 'var(--bg-tertiary)',
          borderRadius: '4px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${percentage}%`,
            height: '100%',
            background: colorStyles[color] || colorStyles.primary,
            borderRadius: '4px',
          }}
        />
      </div>
    </div>
  );
}
