import React, { forwardRef, useState, useId } from 'react';
import { Eye, EyeOff } from 'lucide-react';

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
  const generatedId = useId();
  const inputId = id || generatedId;
  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const isPassword = type === 'password';
  const inputType = isPassword && isPasswordVisible ? 'text' : type;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '100%' }}>
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
          type={inputType}
          style={{
            width: '100%',
            minHeight: 40,
            padding: '8px 12px',
            paddingLeft: leftIcon ? '36px' : '12px',
            paddingRight: isPassword || rightIcon ? '44px' : '12px',
            fontSize: '0.875rem',
            backgroundColor: 'var(--bg-input)',
            color: 'var(--text-primary)',
            border: `1px solid ${error ? 'var(--danger)' : 'var(--field-border)'}`,
            borderRadius: 'var(--radius-md)',
            transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
          }}
          className={`input-field ${className}`}
          {...props}
        />

        {isPassword ? (
          <button
            type="button"
            onClick={() => setIsPasswordVisible((visible) => !visible)}
            aria-label={isPasswordVisible ? 'Hide password' : 'Show password'}
            title={isPasswordVisible ? 'Hide password' : 'Show password'}
            style={{
              position: 'absolute',
              right: '0.5rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '0.25rem',
              color: 'var(--text-muted)',
              background: 'transparent',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
            }}
          >
            {isPasswordVisible ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        ) : rightIcon && (
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
