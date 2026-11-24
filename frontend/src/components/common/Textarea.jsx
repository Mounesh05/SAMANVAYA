import React, { forwardRef, useId } from 'react';

export const Textarea = forwardRef(function Textarea({ label, error, helperText, id, ...props }, ref) {
  const generated = useId();
  const fieldId = id || generated;
  const helpId = `${fieldId}-help`;
  return <div className="scoring-field">
    <label htmlFor={fieldId}>{label}</label>
    <textarea ref={ref} id={fieldId} aria-invalid={Boolean(error)} aria-describedby={error || helperText ? helpId : undefined}
      className="input-field" style={{ resize: 'none', minHeight: '7rem', padding: '.75rem', color: 'var(--text-primary)',
        background: 'var(--bg-input)', border: '1px solid var(--field-border)', borderRadius: 'var(--radius-md)', width: '100%' }} {...props} />
    {(error || helperText) && <p id={helpId} className={error ? 'scoring-error' : 'scoring-help'}>{error || helperText}</p>}
  </div>;
});
