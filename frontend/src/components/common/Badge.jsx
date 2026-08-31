import React from 'react';

export function Badge({
  children,
  variant = 'default', // 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'purple' | 'cyan'
  size = 'md', // 'sm' | 'md'
  style = {},
  className = '',
}) {
  const variantStyles = {
    default: {
      background: 'rgba(255, 255, 255, 0.08)',
      color: 'var(--text-secondary)',
      border: '1px solid var(--border-subtle)',
    },
    primary: {
      background: 'var(--primary-light)',
      color: 'var(--primary)',
      border: '1px solid var(--border-accent)',
    },
    success: {
      background: 'var(--success-light)',
      color: 'var(--success)',
      border: '1px solid var(--success-border)',
    },
    warning: {
      background: 'var(--warning-light)',
      color: 'var(--warning)',
      border: '1px solid var(--warning-border)',
    },
    danger: {
      background: 'var(--danger-light)',
      color: 'var(--danger)',
      border: '1px solid var(--danger-border)',
    },
    info: {
      background: 'var(--info-light)',
      color: 'var(--info)',
      border: '1px solid rgba(56, 189, 248, 0.3)',
    },
    purple: {
      background: 'var(--purple-light)',
      color: 'var(--purple)',
      border: '1px solid rgba(168, 85, 247, 0.3)',
    },
    cyan: {
      background: 'var(--cyan-light)',
      color: 'var(--cyan)',
      border: '1px solid rgba(6, 182, 212, 0.3)',
    },
  };

  const sizeStyles = {
    sm: { padding: '0.15rem 0.5rem', fontSize: '0.7rem' },
    md: { padding: '0.25rem 0.65rem', fontSize: '0.775rem' },
  };

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        fontWeight: '600',
        borderRadius: 'var(--radius-full)',
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        ...sizeStyles[size],
        ...variantStyles[variant],
        ...style,
      }}
      className={`badge ${className}`}
    >
      {children}
    </span>
  );
}
