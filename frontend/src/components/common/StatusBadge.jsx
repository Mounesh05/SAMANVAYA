import React from 'react';
import { Badge } from './Badge';
import { STATUS_LABELS } from '../../utils/constants';

export function StatusBadge({ status, size = 'sm' }) {
  const normalized = String(status || '').toLowerCase();

  let variant = 'default';
  if (['done', 'completed', 'success'].includes(normalized)) variant = 'success';
  else if (['in_progress', 'running'].includes(normalized)) variant = 'primary';
  else if (['review', 'pending'].includes(normalized)) variant = 'purple';
  else if (['blocked', 'failed'].includes(normalized)) variant = 'danger';

  const label = STATUS_LABELS[normalized] || normalized.replace('_', ' ');

  return (
    <Badge variant={variant} size={size}>
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          backgroundColor: 'currentColor',
        }}
      />
      {label}
    </Badge>
  );
}
