import React from 'react';
import { Card } from './Card';
import { getGradeColor } from '../../utils/formatters';
import { scoringPresentation } from '../../utils/performanceScoring';

export function ScoreCard({
  title = 'Performance score',
  score = null,
  grade = 'N/A',
  aiScore = null,
  humanScore = null,
  confidence = null,
  period = null,
  scoring = null,
}) {
  const gradeColor = getGradeColor(grade);
  const presentation = scoringPresentation(scoring, score);
  const shownScore = presentation.score;

  return (
    <Card
      padding="lg"
      style={{
        background: 'var(--bg-card-solid)',
        border: '1px solid var(--border-default)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <p className="scorecard-status" data-approved={presentation.approved}>{presentation.label}</p>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
              {title}
            </span>
            {period && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {period}
              </span>
            )}
          </div>

          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.75rem', marginTop: '0.5rem' }}>
            <span style={{ fontSize: '3rem', fontWeight: '600', color: 'var(--text-primary)', letterSpacing: '-0.04em' }}>
              {shownScore == null ? '—' : shownScore.toFixed(1)}
            </span>
            {shownScore != null && (
              <span style={{ fontSize: '1.25rem', color: 'var(--text-muted)', fontWeight: '600' }}>/ 100</span>
            )}

            {presentation.legacy && grade && grade !== 'N/A' && <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '0.25rem 0.85rem',
                borderRadius: 'var(--radius-lg)',
                backgroundColor: `${gradeColor}20`,
                color: gradeColor,
                border: `1px solid ${gradeColor}50`,
                fontWeight: '500',
                fontSize: '1.25rem',
                marginLeft: '0.5rem',
              }}
            >
              Grade {grade}
            </div>}
          </div>
        </div>

        {/* Optional advisory breakdown */}
        {(!scoring && (aiScore !== null || humanScore !== null)) && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
              padding: '12px 16px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-subtle)',
              width: 'min(100%, 240px)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>AI evaluation</span>
              <span style={{ fontWeight: '600', color: 'var(--cyan)' }}>
                {aiScore !== null ? `${Number(aiScore).toFixed(1)}%` : '—'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Human feedback</span>
              <span style={{ fontWeight: '600', color: 'var(--purple)' }}>
                {humanScore !== null ? `${Number(humanScore).toFixed(1)}%` : '—'}
              </span>
            </div>
            {confidence && (
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', paddingTop: '8px', borderTop: '1px solid var(--border-subtle)' }}>
                <span style={{ color: 'var(--text-muted)' }}>Confidence</span>
                <span style={{ color: 'var(--text-secondary)', fontWeight: '600' }}>{confidence}%</span>
              </div>
            )}
          </div>
        )}
      </div>
      {presentation.legacy && <p className="scorecard-note">Preserved historical value; methodology and comparability remain unverified.</p>}
      {!presentation.legacy && !presentation.approved && <p className="scorecard-note">Missing evidence, policy or approval is not a zero score.</p>}
    </Card>
  );
}
