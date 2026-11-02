import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ScoreCard } from './ScoreCard';

describe('ScoreCard', () => {
  it('shows an unavailable marker instead of a score when no result exists', () => {
    render(<ScoreCard />);

    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.queryByText('/ 100')).not.toBeInTheDocument();
    expect(screen.getByText('Grade N/A')).toBeInTheDocument();
  });

  it('preserves a valid zero score', () => {
    render(<ScoreCard score={0} />);

    expect(screen.getByText('0.0')).toBeInTheDocument();
    expect(screen.getByText('/ 100')).toBeInTheDocument();
  });
});
