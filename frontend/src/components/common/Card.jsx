import React from 'react';

export function Card({
  children,
  title,
  subtitle,
  action,
  className = '',
  style = {},
  variant = 'glass', // 'glass' | 'solid' | 'flat'
  padding = 'md', // 'none' | 'sm' | 'md' | 'lg'
  onClick,
  ...props
}) {
  const paddingMap = {
    none: '0',
    sm: '0.85rem',
    md: '1.25rem',
    lg: '1.75rem',
  };

  const variantStyles = {
    glass: {
      background: 'var(--bg-glass-card)',
      backdropFilter: 'blur(16px)',
      WebkitBackdropFilter: 'blur(16px)',
      border: '1px solid var(--border-subtle)',
    },
    solid: {
      background: 'var(--bg-card-solid)',
      border: '1px solid var(--border-default)',
    },
    flat: {
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border-subtle)',
    },
  };

  return (
    <div
      style={{
        borderRadius: 'var(--radius-lg)',
        padding: paddingMap[padding],
        boxShadow: 'var(--shadow-md)',
        transition: 'transform var(--transition-base), box-shadow var(--transition-base), border-color var(--transition-base)',
        cursor: onClick ? 'pointer' : 'default',
        ...variantStyles[variant],
        ...style,
      }}
      className={`card ${className}`}
      onClick={onClick}
      {...props}
    >
      {(title || action) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '1rem',
            paddingBottom: '0.5rem',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <div>
            {title && (
              <h3 style={{ fontSize: '1rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                {title}
              </h3>
            )}
            {subtitle && (
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
                {subtitle}
              </p>
            )}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
