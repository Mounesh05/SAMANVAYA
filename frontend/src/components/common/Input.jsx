import React, { forwardRef } from 'react';

export const Input = forwardRef(function Input(
  {
    label,
    error,
    helperText,
    leftIcon = null,
    rightIcon = null,
    className = '',
    required = false,
    id,
    type = 'text',
    ...props
  },
  ref
) {
  const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', width: '100%' }}>
      {label && (
        <label
          htmlFor={inputId}
          style={{
            fontSize: '0.8125rem',
            fontWeight: '600',
            color: 'var(--text-secondary)',
          }}
        >
          {label} {required && <span style={{ color: 'var(--danger)' }}>*</span>}
        </label>
      )}

      <div
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          width: '100%',
        }}
      >
        {leftIcon && (
          <div
            style={{
              position: 'absolute',
              left: '0.75rem',
              color: 'var(--text-muted)',
              display: 'flex',
              alignItems: 'center',
              pointerEvents: 'none',
            }}
          >
            {leftIcon}
          </div>
        )}

        <input
          ref={ref}
          id={inputId}
          type={type}
          style={{
            width: '100%',
            padding: '0.55rem 0.85rem',
            paddingLeft: leftIcon ? '2.4rem' : '0.85rem',
            paddingRight: rightIcon ? '2.4rem' : '0.85rem',
            fontSize: '0.875rem',
            backgroundColor: 'var(--bg-input)',
            color: 'var(--text-primary)',
            border: `1px solid ${error ? 'var(--danger)' : 'var(--border-default)'}`,
            borderRadius: 'var(--radius-md)',
            outline: 'none',
            transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
          }}
          className={`input-field ${className}`}
          {...props}
        />

        {rightIcon && (
          <div
            style={{
              position: 'absolute',
              right: '0.75rem',
              color: 'var(--text-muted)',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {rightIcon}
          </div>
        )}
      </div>

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
