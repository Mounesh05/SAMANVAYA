import React from 'react';

export function ProgressBar({
  value = 0,
  max = 100,
  color = 'primary', // 'primary' | 'success' | 'warning' | 'danger' | 'cyan' | 'purple'
  showLabel = false,
  height = '8px',
  className = '',
}) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  const colorStyles = {
    primary: 'linear-gradient(90deg, #3b82f6 0%, #60a5fa 100%)',
    success: 'linear-gradient(90deg, #10b981 0%, #34d399 100%)',
    warning: 'linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%)',
    danger: 'linear-gradient(90deg, #ef4444 0%, #f87171 100%)',
    cyan: 'linear-gradient(90deg, #06b6d4 0%, #38bdf8 100%)',
    purple: 'linear-gradient(90deg, #a855f7 0%, #c084fc 100%)',
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
          backgroundColor: 'rgba(255, 255, 255, 0.08)',
          borderRadius: 'var(--radius-full)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${percentage}%`,
            height: '100%',
            background: colorStyles[color] || colorStyles.primary,
            borderRadius: 'var(--radius-full)',
            transition: 'width 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        />
      </div>
    </div>
  );
}
