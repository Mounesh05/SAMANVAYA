import { useState, useEffect } from 'react';
import { AlertTriangle, Check, X } from 'lucide-react';

/**
 * ConfirmToast – a reusable confirmation banner.
 *
 * Props:
 *   message   – string   – the question shown to the user
 *   onConfirm – () => void
 *   onCancel  – () => void
 *   variant   – 'danger' | 'warning' | 'info'  (default 'danger')
 */
export default function ConfirmToast({ message, onConfirm, onCancel, variant = 'danger' }) {
    const [visible, setVisible] = useState(false);

    useEffect(() => { requestAnimationFrame(() => setVisible(true)); }, []);

    const colors = {
        danger: { bg: '#fef2f2', border: '#fca5a5', accent: '#ef4444', text: '#991b1b' },
        warning: { bg: '#fffbeb', border: '#fcd34d', accent: '#f59e0b', text: '#92400e' },
        info: { bg: '#eff6ff', border: '#93c5fd', accent: '#3b82f6', text: '#1e3a5f' },
    };
    const c = colors[variant] || colors.danger;

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center',
            justifyContent: 'center', zIndex: 9999,
            opacity: visible ? 1 : 0, transition: 'opacity 0.2s ease',
        }}>
            <div style={{
                background: '#fff', borderRadius: 14, padding: '28px 32px',
                maxWidth: 420, width: '90vw', boxShadow: '0 20px 60px rgba(0,0,0,0.18)',
                border: `1px solid ${c.border}`,
                transform: visible ? 'scale(1)' : 'scale(0.92)',
                transition: 'transform 0.2s ease',
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                    <div style={{
                        width: 36, height: 36, borderRadius: '50%',
                        background: `${c.accent}15`, display: 'flex',
                        alignItems: 'center', justifyContent: 'center',
                    }}>
                        <AlertTriangle size={18} color={c.accent} />
                    </div>
                    <h3 style={{ margin: 0, fontSize: '1rem', color: c.text }}>Confirm Action</h3>
                </div>
                <p style={{ margin: '0 0 20px', fontSize: '0.9rem', color: '#374151', lineHeight: 1.5 }}>
                    {message}
                </p>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                    <button
                        onClick={onCancel}
                        style={{
                            padding: '8px 18px', borderRadius: 8, border: '1px solid #d1d5db',
                            background: '#fff', color: '#374151', fontWeight: 600,
                            fontSize: '0.85rem', cursor: 'pointer',
                        }}>
                        <X size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        style={{
                            padding: '8px 18px', borderRadius: 8, border: 'none',
                            background: c.accent, color: '#fff', fontWeight: 600,
                            fontSize: '0.85rem', cursor: 'pointer',
                        }}>
                        <Check size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Confirm
                    </button>
                </div>
            </div>
        </div>
    );
}
