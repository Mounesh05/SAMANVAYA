import React, { useEffect, useId, useRef } from 'react';
import { X } from 'lucide-react';

export function Modal({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  maxWidth = '550px',
  footer = null,
}) {
  const titleId = useId();
  const subtitleId = useId();
  const dialog = useRef(null);
  useEffect(() => {
    if (!isOpen) return;
    const opener = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    if (!dialog.current.contains(document.activeElement)) {
      dialog.current.querySelector('button')?.focus();
    }
    return () => {
      document.body.style.overflow = previousOverflow;
      if (opener?.isConnected) opener.focus();
    };
  }, [isOpen]);

  function handleKeyDown(event) {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onClose();
    }
    if (event.key !== 'Tab') return;
    const controls = Array.from(dialog.current.querySelectorAll(
      'button, a[href], input:not([type="hidden"]), select, textarea, summary, [tabindex]'
    )).filter((control) => control.tabIndex >= 0 && !control.matches(':disabled')
      && !control.closest('[hidden], [inert], [aria-hidden="true"]')
      && (control.closest('details:not([open])') == null || control.tagName === 'SUMMARY'));
    const first = controls[0];
    const last = controls.at(-1);
    if (event.shiftKey ? document.activeElement === first : document.activeElement === last) {
      event.preventDefault();
      (event.shiftKey ? last : first)?.focus();
    }
  }

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
        backgroundColor: 'rgba(0, 0, 0, 0.7)',
      }}
      onClick={onClose}
    >
      <div
        ref={dialog}
        onKeyDown={handleKeyDown}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={subtitle ? subtitleId : undefined}
        style={{
          width: '100%',
          maxWidth,
          maxHeight: '90vh',
          backgroundColor: 'var(--bg-secondary)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-xl)',
          boxShadow: 'var(--shadow-xl)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'fadeIn var(--transition-base)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <div>
            <h3 id={titleId} style={{ fontSize: '1.125rem', fontWeight: '600', color: 'var(--text-primary)' }}>
              {title}
            </h3>
            {subtitle && (
              <p id={subtitleId} style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                {subtitle}
              </p>
            )}
          </div>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '8px',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'color var(--transition-fast)',
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div
          style={{
            padding: '1.5rem',
            overflowY: 'auto',
            flex: 1,
          }}
        >
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div
            style={{
              padding: '1rem 1.5rem',
              borderTop: '1px solid var(--border-subtle)',
              backgroundColor: 'var(--bg-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              flexWrap: 'wrap',
              gap: '0.75rem',
            }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
