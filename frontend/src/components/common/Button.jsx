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
    fontWeight: '600',
    borderRadius: 'var(--radius-md)',
    transition: 'all var(--transition-fast)',
    cursor: disabled || isLoading ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    borderWidth: '1px',
    borderStyle: 'solid',
    borderColor: 'transparent',
    outline: 'none',
  };

  const sizeStyles = {
    sm: { padding: '0.35rem 0.75rem', fontSize: '0.8125rem' },
    md: { padding: '0.55rem 1.15rem', fontSize: '0.875rem' },
    lg: { padding: '0.75rem 1.6rem', fontSize: '1rem' },
  };

  const variantStyles = {
    primary: {
      background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
      color: '#ffffff',
      boxShadow: '0 2px 10px rgba(37, 99, 235, 0.3)',
      borderColor: 'transparent',
    },
    secondary: {
      background: 'var(--bg-elevated)',
      color: 'var(--text-primary)',
      borderColor: 'var(--border-default)',
    },
    outline: {
      background: 'transparent',
      color: 'var(--text-primary)',
      borderColor: 'var(--border-default)',
    },
    danger: {
      background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
      color: '#ffffff',
      boxShadow: '0 2px 10px rgba(220, 38, 38, 0.3)',
      borderColor: 'transparent',
    },
    ghost: {
      background: 'transparent',
      color: 'var(--text-secondary)',
      borderColor: 'transparent',
    },
    glass: {
      background: 'rgba(255, 255, 255, 0.05)',
      color: 'var(--text-primary)',
      borderColor: 'var(--border-subtle)',
      backdropFilter: 'blur(8px)',
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
      className={`btn-${variant} ${className}`}
      {...props}
    >
      {isLoading ? <Loader2 size={16} className="animate-spin" /> : leftIcon}
      {children}
      {!isLoading && rightIcon}
    </button>
  );
}
