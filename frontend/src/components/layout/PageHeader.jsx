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
    <header className={`page-header ${className}`}>
      <div>
        {breadcrumbs && <div className="page-header-breadcrumbs">{breadcrumbs}</div>}
        <div className="page-header-title">
          <h1>{title}</h1>
          {badge}
        </div>
        {subtitle && <p className="page-header-description">{subtitle}</p>}
      </div>

      {actions && <div className="page-header-actions">{actions}</div>}
    </header>
  );
}
