import React from 'react';
import { Card } from './Card';
import { getGradeColor } from '../../utils/formatters';

export function ScoreCard({
  title = 'Performance Score',
  score = 0,
  grade = 'N/A',
  aiScore = null,
  humanScore = null,
  confidence = null,
  period = null,
}) {
  const gradeColor = getGradeColor(grade);

  return (
    <Card
      padding="lg"
      style={{
        background: 'linear-gradient(135deg, rgba(19, 29, 46, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%)',
        border: '1px solid var(--border-default)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.875rem', fontWeight: '700', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              {title}
            </span>
            {period && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', background: 'var(--bg-elevated)', padding: '0.15rem 0.5rem', borderRadius: 'var(--radius-full)' }}>
                {period}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.75rem', marginTop: '0.5rem' }}>
            <span style={{ fontSize: '3rem', fontWeight: '900', color: 'var(--text-primary)', letterSpacing: '-0.04em' }}>
              {typeof score === 'number' ? score.toFixed(1) : score}
            </span>
            <span style={{ fontSize: '1.25rem', color: 'var(--text-muted)', fontWeight: '600' }}>/ 100</span>

            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0.25rem 0.85rem',
                borderRadius: 'var(--radius-lg)',
                backgroundColor: `${gradeColor}20`,
                color: gradeColor,
                border: `1px solid ${gradeColor}50`,
                fontWeight: '800',
                fontSize: '1.25rem',
                marginLeft: '0.5rem',
              }}
            >
              Grade {grade}
            </div>
          </div>
        </div>

        {/* 90% AI + 10% Human breakdown */}
        {(aiScore !== null || humanScore !== null) && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
              padding: '0.85rem 1.15rem',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid var(--border-subtle)',
              minWidth: '200px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>AI Evaluation (90%)</span>
              <span style={{ fontWeight: '700', color: 'var(--cyan)' }}>
                {aiScore !== null ? `${Number(aiScore).toFixed(1)}%` : '—'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Human Feedback (10%)</span>
              <span style={{ fontWeight: '700', color: 'var(--purple)' }}>
                {humanScore !== null ? `${Number(humanScore).toFixed(1)}%` : '—'}
              </span>
            </div>
            {confidence && (
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', paddingTop: '0.35rem', borderTop: '1px solid var(--border-subtle)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Confidence</span>
                <span style={{ color: 'var(--text-secondary)', fontWeight: '600' }}>{confidence}%</span>
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
