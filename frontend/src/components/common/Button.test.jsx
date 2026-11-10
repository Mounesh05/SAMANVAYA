import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import React from 'react';
import { Button } from './Button';

describe('Button Component', () => {
  it('does not emit React DOM style conflict warnings across variant rerenders', () => {
    const errorSpy = vi.spyOn(console, 'error');

    const { rerender } = render(<Button variant="primary">Click</Button>);
    expect(errorSpy).not.toHaveBeenCalled();

    // Rerender variant to secondary (which has border-default)
    rerender(<Button variant="secondary">Click</Button>);
    expect(errorSpy).not.toHaveBeenCalled();

    // Rerender variant to outline
    rerender(<Button variant="outline">Click</Button>);
    expect(errorSpy).not.toHaveBeenCalled();

    // Rerender variant to glass
    rerender(<Button variant="glass">Click</Button>);
    expect(errorSpy).not.toHaveBeenCalled();

    // Rerender variant to danger
    rerender(<Button variant="danger">Click</Button>);
    expect(errorSpy).not.toHaveBeenCalled();

    // Rerender variant to ghost
    rerender(<Button variant="ghost">Click</Button>);
    expect(errorSpy).not.toHaveBeenCalled();

    // Rerender variant back to primary
    rerender(<Button variant="primary">Click</Button>);
    expect(errorSpy).not.toHaveBeenCalled();

    errorSpy.mockRestore();
  });

  it('does not emit style conflict warnings during state transitions (disabled, isLoading)', () => {
    const errorSpy = vi.spyOn(console, 'error');

    const { rerender } = render(<Button variant="secondary">Click</Button>);
    expect(errorSpy).not.toHaveBeenCalled();

    rerender(<Button variant="secondary" disabled>Click</Button>);
    expect(errorSpy).not.toHaveBeenCalled();

    rerender(<Button variant="secondary" isLoading>Click</Button>);
    expect(errorSpy).not.toHaveBeenCalled();

    rerender(<Button variant="secondary" disabled={false} isLoading={false}>Click</Button>);
    expect(errorSpy).not.toHaveBeenCalled();

    errorSpy.mockRestore();
  });

  it('merges custom style prop cleanly with base styles', () => {
    render(
      <Button variant="primary" style={{ marginTop: '20px', zIndex: 10 }}>
        Styled
      </Button>
    );

    const button = screen.getByRole('button', { name: 'Styled' });
    expect(button.style.marginTop).toBe('20px');
    expect(button.style.zIndex).toBe('10');
    expect(button.style.borderWidth).toBe('1px');
    expect(button.style.borderStyle).toBe('solid');
    expect(button.style.borderColor).toBe('transparent');
  });

  it('handles click events and respects disabled/loading state', () => {
    const handleClick = vi.fn();
    const { rerender } = render(<Button onClick={handleClick}>Action</Button>);

    const button = screen.getByRole('button', { name: 'Action' });
    fireEvent.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);

    rerender(<Button onClick={handleClick} disabled>Action</Button>);
    fireEvent.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
