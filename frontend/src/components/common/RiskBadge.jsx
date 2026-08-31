import React from 'react';
import { Badge } from './Badge';
import { AlertTriangle, AlertCircle, ShieldCheck } from 'lucide-react';

export function RiskBadge({ level, score = null, size = 'sm' }) {
  const normalized = String(level || '').toUpperCase();

  let variant = 'default';
  let Icon = ShieldCheck;

  if (normalized === 'CRITICAL') {
    variant = 'danger';
    Icon = AlertTriangle;
  } else if (normalized === 'HIGH') {
    variant = 'danger';
    Icon = AlertCircle;
  } else if (normalized === 'MEDIUM') {
    variant = 'warning';
    Icon = AlertCircle;
  } else if (normalized === 'LOW') {
    variant = 'success';
    Icon = ShieldCheck;
  }

  return (
    <Badge variant={variant} size={size}>
      <Icon size={12} />
      {normalized} {score !== null && `(${score})`}
    </Badge>
  );
}
