import React from 'react';
import { Card } from './Card';
import { ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';

export function MetricCard({
  title,
  value,
  subtitle,
  icon = null,
  trend = null, // { value: number | string, direction: 'up' | 'down' | 'neutral', label: string }
  color = 'primary', // 'primary' | 'cyan' | 'purple' | 'success' | 'warning' | 'danger'
  className = '',
  onClick,
}) {
  const colorMap = {
    primary: { glow: 'var(--shadow-glow-blue)', text: '#3b82f6', bg: 'var(--primary-light)' },
    cyan: { glow: 'var(--shadow-glow-cyan)', text: '#06b6d4', bg: 'var(--cyan-light)' },
    purple: { glow: 'var(--shadow-glow-purple)', text: '#a855f7', bg: 'var(--purple-light)' },
    success: { glow: '0 0 20px rgba(16, 185, 129, 0.3)', text: '#10b981', bg: 'var(--success-light)' },
    warning: { glow: '0 0 20px rgba(245, 158, 11, 0.3)', text: '#f59e0b', bg: 'var(--warning-light)' },
    danger: { glow: '0 0 20px rgba(239, 68, 68, 0.3)', text: '#ef4444', bg: 'var(--danger-light)' },
  };

  const currentTheme = colorMap[color] || colorMap.primary;

  return (
    <Card
      padding="md"
      className={`metric-card ${className}`}
      onClick={onClick}
      style={{
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-muted)' }}>
            {title}
          </span>
          <div
            style={{
              fontSize: '1.75rem',
              fontWeight: '800',
              color: 'var(--text-primary)',
              marginTop: '0.25rem',
              letterSpacing: '-0.03em',
            }}
          >
            {value}
          </div>
        </div>

        {icon && (
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: 'var(--radius-lg)',
              backgroundColor: currentTheme.bg,
              color: currentTheme.text,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            {icon}
          </div>
        )}
      </div>

      {(subtitle || trend) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            marginTop: '0.85rem',
            fontSize: '0.8125rem',
          }}
        >
          {trend && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.2rem',
                fontWeight: '600',
                color:
                  trend.direction === 'up'
                    ? 'var(--success)'
                    : trend.direction === 'down'
                    ? 'var(--danger)'
                    : 'var(--text-muted)',
              }}
            >
              {trend.direction === 'up' && <ArrowUpRight size={14} />}
              {trend.direction === 'down' && <ArrowDownRight size={14} />}
              {trend.direction === 'neutral' && <Minus size={14} />}
              {trend.value}
            </span>
          )}
          {subtitle && (
            <span style={{ color: 'var(--text-muted)' }}>
              {subtitle}
            </span>
          )}
        </div>
      )}
    </Card>
  );
}
