import React, { forwardRef } from 'react';

export const Select = forwardRef(function Select(
  {
    label,
    options = [],
    error,
    helperText,
    required = false,
    id,
    className = '',
    placeholder = 'Select an option',
    ...props
  },
  ref
) {
  const selectId = id || `select-${Math.random().toString(36).substr(2, 9)}`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', width: '100%' }}>
      {label && (
        <label
          htmlFor={selectId}
          style={{
            fontSize: '0.8125rem',
            fontWeight: '600',
            color: 'var(--text-secondary)',
          }}
        >
          {label} {required && <span style={{ color: 'var(--danger)' }}>*</span>}
        </label>
      )}

      <select
        ref={ref}
        id={selectId}
        style={{
          width: '100%',
          padding: '0.55rem 0.85rem',
          fontSize: '0.875rem',
          backgroundColor: 'var(--bg-input)',
          color: 'var(--text-primary)',
          border: `1px solid ${error ? 'var(--danger)' : 'var(--border-default)'}`,
          borderRadius: 'var(--radius-md)',
          outline: 'none',
          cursor: 'pointer',
        }}
        className={`select-field ${className}`}
        {...props}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((opt) => {
          const val = typeof opt === 'object' ? opt.value : opt;
          const lbl = typeof opt === 'object' ? opt.label : opt;
          return (
            <option key={val} value={val} style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}>
              {lbl}
            </option>
          );
        })}
      </select>

      {error && (
        <span style={{ fontSize: '0.75rem', color: 'var(--danger)', fontWeight: '500' }}>
          {error}
        </span>
      )}
      {!error && helperText && (
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          {helperText}
        </span>
      )}
    </div>
  );
});
