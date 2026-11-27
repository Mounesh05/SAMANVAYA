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
    sm: '16px',
    md: '20px',
    lg: '28px',
  };

  const variantStyles = {
    glass: {
      background: 'var(--bg-card-solid)',
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
        minWidth: 0,
        borderRadius: 'var(--radius-lg)',
        padding: paddingMap[padding],
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
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: '1rem',
            flexWrap: 'wrap',
            marginBottom: '16px',
            paddingBottom: '0.75rem',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <div>
            {title && (
              <h3 style={{ fontSize: '1rem', fontWeight: '600', color: 'var(--text-primary)' }}>
                {title}
              </h3>
            )}
            {subtitle && (
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                {subtitle}
              </p>
            )}
          </div>
          {action && <div style={{ flexShrink: 0 }}>{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
