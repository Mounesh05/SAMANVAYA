import React from 'react';
import { Card } from './Card';
import { scoringPresentation } from '../../utils/performanceScoring';
import '../performance/scoring.css';

export function ScoreCard({ title = 'Performance record', score = null, grade = null, period = null, scoring = null }) {
  const presentation = scoringPresentation(scoring, score);
  return <Card padding="lg">
    <div className="scoring-stack">
      <div><strong>{title}</strong>{period && <p className="scoring-help">{period}</p>}</div>
      <div><span className="scoring-status" data-approved={presentation.approved}>{presentation.label}</span></div>
      <div><span className="scoring-number">{presentation.score === null ? '—' : presentation.score.toFixed(1)}</span>
        {presentation.score !== null && <span> / 100</span>}</div>
      {presentation.legacy && grade && grade !== 'N/A' && <p>Historical grade {grade}</p>}
      {presentation.legacy && <p className="scoring-help">Preserved historical value. It is not a canonical approved score and cannot establish a comparable performance trend.</p>}
      {!presentation.approved && !presentation.legacy && <p className="scoring-help">Missing evidence, policy or approval is not a zero score.</p>}
    </div>
  </Card>;
}
