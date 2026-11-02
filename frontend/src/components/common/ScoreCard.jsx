/**
 * ScoreCard and MetricCard display components
 */
import { scoreColor, formatPercent } from '../../utils/formatters';

export function ScoreCard({ label, score, subtitle, className = '' }) {
  const colorClass = scoreColor(score);
  return (
    <div className={`card ${className}`} style={{ textAlign: 'center' }}>
      <div className={`score-value-lg ${colorClass}`}>{formatPercent(score)}</div>
      <div className="score-label" style={{ marginTop: 4 }}>{label}</div>
      {subtitle && <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 4 }}>{subtitle}</div>}
    </div>
  );
}

export function MetricCard({ label, value, icon: Icon, change, changePositive, iconBg = 'var(--bg-elevated)', iconColor = 'var(--brand-400)' }) {
  return (
    <div className="metric-card">
      {Icon && (
        <div className="metric-icon" style={{ background: iconBg, color: iconColor }}>
          <Icon size={18} />
        </div>
      )}
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value ?? '—'}</div>
      {change !== undefined && (
        <div className={`metric-change ${changePositive ? 'positive' : 'negative'}`}>
          {changePositive ? '↑' : '↓'} {change}
        </div>
      )}
    </div>
  );
}

export function ProgressBar({ value = 0, max = 100, variant }) {
  const pct = Math.min(100, Math.round((value / max) * 100));
  return (
    <div className="progress-bar" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={max}>
      <div
        className={`progress-fill${variant ? ` ${variant}` : ''}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
