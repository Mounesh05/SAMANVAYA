import React from 'react';
import { Loader2 } from 'lucide-react';

export function Button({
  children,
  variant = 'primary', // 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost' | 'glass'
  size = 'md', // 'sm' | 'md' | 'lg'
  isLoading = false,
  disabled = false,
  leftIcon = null,
  rightIcon = null,
  className = '',
  type = 'button',
  onClick,
  style = {},
  ...props
}) {
  const baseStyles = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
    fontWeight: '500',
    borderRadius: 'var(--radius-md)',
    transition: 'background-color var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast)',
    cursor: disabled || isLoading ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    borderWidth: '1px',
    borderStyle: 'solid',
    borderColor: 'transparent',
  };

  const sizeStyles = {
    sm: { minHeight: 32, padding: '4px 12px', fontSize: '0.8125rem' },
    md: { minHeight: 36, padding: '8px 16px', fontSize: '0.875rem' },
    lg: { minHeight: 44, padding: '8px 20px', fontSize: '0.9375rem' },
  };

  const variantStyles = {
    primary: {
      backgroundColor: 'var(--button-fill, var(--action))',
      color: '#ffffff',
      borderColor: 'transparent',
    },
    secondary: {
      backgroundColor: 'var(--button-fill, var(--bg-elevated))',
      color: 'var(--text-primary)',
      borderColor: 'var(--border-default)',
    },
    outline: {
      backgroundColor: 'var(--button-fill, transparent)',
      color: 'var(--text-primary)',
      borderColor: 'var(--border-default)',
    },
    danger: {
      backgroundColor: 'var(--button-fill, var(--action-danger))',
      color: '#ffffff',
      borderColor: 'transparent',
    },
    ghost: {
      backgroundColor: 'var(--button-fill, transparent)',
      color: 'var(--text-secondary)',
      borderColor: 'transparent',
    },
    glass: {
      backgroundColor: 'var(--button-fill, var(--bg-secondary))',
      color: 'var(--text-primary)',
      borderColor: 'var(--border-subtle)',
    },
  };

  return (
    <button
      type={type}
      disabled={disabled || isLoading}
      onClick={onClick}
      style={{
        ...baseStyles,
        ...sizeStyles[size],
        ...variantStyles[variant],
        ...style,
      }}
      aria-busy={isLoading || undefined}
      className={`button btn-${variant} ${className}`}
      {...props}
    >
      {isLoading ? <Loader2 size={16} className="animate-spin" aria-hidden="true" /> : leftIcon}
      {children}
      {!isLoading && rightIcon}
    </button>
  );
}
