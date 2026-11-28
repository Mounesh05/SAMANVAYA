import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AIInterpretation, ReportStatusNotice, dependencyAuditLabel } from '../pages/code-quality/AIInterpretation';

const completed = {
  status: 'completed', analysis: 'One unused import was added.', errors: [],
  critical_issues: [], recommendations: ['[a.py:3 RUFF-F401] Remove the unused import.'],
  evidence_basis: ['1 analyzer finding(s) from 1 analysed file(s) were given to the model.',
    'Base vs head quality score: 90 -> 88; findings new 1, unchanged 0, resolved 0.'],
};

describe('AI interpretation card', () => {
  it('shows a short summary, cited points and collapsible evidence', () => {
    render(<AIInterpretation ai={completed} />);
    expect(screen.getByText('AI interpretation')).toBeInTheDocument();
    expect(screen.getByText(/Advisory only/)).toBeInTheDocument();
    expect(screen.getByText('One unused import was added.')).toBeInTheDocument();
    expect(screen.getByText('[a.py:3 RUFF-F401] Remove the unused import.')).toBeInTheDocument();
    const details = screen.getByText('Evidence used (2)').closest('details');
    expect(details.open).toBe(false);
    fireEvent.click(screen.getByText('Evidence used (2)'));
    expect(details.open).toBe(true);
    expect(screen.getByText(/90 -> 88/)).toBeInTheDocument();
  });

  it('says plainly when there is nothing to recommend', () => {
    render(<AIInterpretation ai={{ ...completed, recommendations: [], evidence_basis: [] }} />);
    expect(screen.getByText(/No recommendations/)).toBeInTheDocument();
    expect(screen.queryByText(/Evidence used/)).not.toBeInTheDocument();
  });

  it('explains an interpretation that did not complete', () => {
    render(<AIInterpretation ai={{ status: 'unavailable', errors: ['MODEL_UNAVAILABLE'] }} />);
    expect(screen.getByText(/the AI model could not be reached/)).toBeInTheDocument();
  });

  it('renders nothing for legacy skipped runs', () => {
    const { container } = render(<AIInterpretation ai={{ status: 'skipped', errors: [] }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('marks an incomplete report and labels unaudited dependencies', () => {
    render(<ReportStatusNotice run={{ report_status: 'incomplete' }} />);
    expect(screen.getByRole('status')).toHaveTextContent('Report incomplete');
    expect(dependencyAuditLabel('not_checked_offline')).toMatch(/^not checked/);
    expect(dependencyAuditLabel('checked')).toBe('checked');
  });

  it('renders model text as text, never HTML', () => {
    render(<AIInterpretation ai={{ ...completed, analysis: '<img src=x onerror=alert(1)>' }} />);
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
    expect(document.querySelector('img')).toBeNull();
  });
});
