import React from 'react';

export function Badge({
  children,
  variant = 'default',
  size = 'md', // 'sm' | 'md'
  style = {},
  className = '',
}) {
  const tones = {
    primary: 'var(--primary)',
    info: 'var(--info)',
    success: 'var(--success)',
    warning: 'var(--warning)',
    danger: 'var(--danger)',
    error: 'var(--danger)',
  };

  return (
    <span
      style={{ '--badge-tone': tones[variant], ...style }}
      className={`badge badge-${size} ${className}`}
    >
      {children}
    </span>
  );
}
