import React from 'react';

export function CIProvisioningModal({ isOpen, onClose, onProvision, projectId }) {
  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div style={{
        backgroundColor: 'var(--bg-card, #1e293b)',
        padding: '1.5rem',
        borderRadius: 'var(--radius-lg, 0.5rem)',
        maxWidth: '480px',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem'
      }}>
        <h3 style={{ fontSize: '1.125rem', fontWeight: '700' }}>Provision CI Workflow</h3>
        <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
          Configure automated CI testing workflow for project {projectId}.
        </p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-default)',
              background: 'transparent',
              color: 'var(--text-primary)',
              cursor: 'pointer'
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onProvision && onProvision({ branch: 'main' })}
            style={{
              padding: '0.5rem 1rem',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: 'var(--primary, #3b82f6)',
              color: '#fff',
              cursor: 'pointer'
            }}
          >
            Provision
          </button>
        </div>
      </div>
    </div>
  );
}

