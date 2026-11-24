import React from 'react';
import { ArrowUpRight } from 'lucide-react';
import { Card } from './Card';

export function MetricCard({
  title,
  value,
  subtitle,
  trend = null,
  className = '',
  onClick,
}) {
  return (
    <Card className={`metric-card ${className}`}>
      <div className="metric-card-title">
        {onClick ? (
          <button type="button" className="metric-card-action" onClick={onClick}>
            {title}
            <ArrowUpRight size={16} strokeWidth={1.5} aria-hidden="true" />
          </button>
        ) : title}
      </div>
      <div className="metric-card-value">{value}</div>
      {(subtitle || trend) && (
        <div className="metric-card-meta">
          {trend && <span className="metric-card-trend">{trend.value} {trend.label}</span>}
          {subtitle && <span>{subtitle}</span>}
        </div>
      )}
    </Card>
  );
}
