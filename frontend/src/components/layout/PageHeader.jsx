import React from 'react';

export function PageHeader({
  title,
  subtitle,
  badge = null,
  actions = null,
  breadcrumbs = null,
  className = '',
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '1rem',
        marginBottom: '1.75rem',
      }}
      className={`page-header ${className}`}
    >
      <div>
        {breadcrumbs && <div style={{ marginBottom: '0.4rem' }}>{breadcrumbs}</div>}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <h1
            style={{
              fontSize: '1.75rem',
              fontWeight: '800',
              color: 'var(--text-primary)',
              letterSpacing: '-0.03em',
            }}
          >
            {title}
          </h1>
          {badge}
        </div>
        {subtitle && (
          <p
            style={{
              fontSize: '0.875rem',
              color: 'var(--text-muted)',
              marginTop: '0.25rem',
              maxWidth: '650px',
            }}
          >
            {subtitle}
          </p>
        )}
      </div>

      {actions && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', flexWrap: 'wrap' }}>
          {actions}
        </div>
      )}
    </div>
  );
}
