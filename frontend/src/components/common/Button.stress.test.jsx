import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import React, { useState } from 'react';
import { Button } from './Button';

describe('Button Component Stress & Adversarial Suite', () => {
  let consoleErrorSpy;
  let consoleWarnSpy;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
    consoleWarnSpy.mockRestore();
  });

  it('negative control: verifies console.error catches shorthand/longhand border conflicts', () => {
    // Proves the testing oracle can detect React DOM style property collision warnings
    function BrokenComponent({ variant }) {
      const base = {
        border: '1px solid transparent',
      };
      const vStyle = variant === 'secondary' ? { borderColor: 'red' } : {};
      return <button style={{ ...base, ...vStyle }}>Negative Control</button>;
    }

    const { rerender } = render(<BrokenComponent variant="primary" />);
    rerender(<BrokenComponent variant="secondary" />);
    rerender(<BrokenComponent variant="primary" />);

    const conflictWarnings = consoleErrorSpy.mock.calls.filter(([msg]) =>
      typeof msg === 'string' &&
      (msg.includes('Updating a style property during rerender') ||
       msg.includes('Removing a style property during rerender') ||
       msg.includes('conflicting property'))
    );
    expect(conflictWarnings.length).toBeGreaterThan(0);
    expect(conflictWarnings[0][0]).toContain('shorthand and non-shorthand properties');

    consoleErrorSpy.mockClear();
  });

  it('stress-test: rapid multi-cycle variant switching emits zero console errors or style warnings', () => {
    const variants = ['primary', 'secondary', 'outline', 'danger', 'ghost', 'glass'];

    const { rerender } = render(<Button variant="primary">Rapid Switch</Button>);

    // Perform 60 rapid sequential variant transitions (10 full cycles)
    for (let cycle = 0; cycle < 10; cycle++) {
      for (const variant of variants) {
        rerender(<Button variant={variant}>Rapid Switch</Button>);
      }
    }

    // Explicit check for style warnings
    const styleWarnings = consoleErrorSpy.mock.calls.filter(([msg]) =>
      typeof msg === 'string' &&
      (msg.includes('style property') || msg.includes('border') || msg.includes('Warning:'))
    );

    expect(styleWarnings).toEqual([]);
    expect(consoleErrorSpy).not.toHaveBeenCalled();
    expect(consoleWarnSpy).not.toHaveBeenCalled();
  });

  it('stress-test: simultaneous prop combinations (variant + disabled + isLoading + size + custom style)', () => {
    const variants = ['primary', 'secondary', 'outline', 'danger', 'ghost', 'glass'];
    const sizes = ['sm', 'md', 'lg'];

    function DynamicHarness({ config }) {
      return (
        <Button
          variant={config.variant}
          size={config.size}
          disabled={config.disabled}
          isLoading={config.isLoading}
          style={config.style}
          className={config.className}
        >
          {config.label}
        </Button>
      );
    }

    let config = {
      variant: 'primary',
      size: 'md',
      disabled: false,
      isLoading: false,
      style: { borderColor: '#10b981' },
      className: 'custom-btn-1',
      label: 'Initial',
    };

    const { rerender } = render(<DynamicHarness config={config} />);

    // Cycle through permutation matrix
    for (let i = 0; i < 30; i++) {
      const variant = variants[i % variants.length];
      const size = sizes[i % sizes.length];
      const disabled = i % 2 === 0;
      const isLoading = i % 3 === 0;
      const customBorder = i % 4 === 0 ? 'rgb(239, 68, 68)' : undefined;

      config = {
        variant,
        size,
        disabled,
        isLoading,
        style: customBorder ? { borderColor: customBorder, zIndex: i } : { opacity: 0.9 },
        className: `stress-test-${i}`,
        label: `Step ${i}`,
      };

      rerender(<DynamicHarness config={config} />);

      const btn = screen.getByRole('button');
      expect(btn).toBeInTheDocument();
      if (disabled || isLoading) {
        expect(btn).toBeDisabled();
      } else {
        expect(btn).not.toBeDisabled();
      }

      if (customBorder) {
        expect(btn.style.borderColor).toBe(customBorder);
      }
    }

    const styleErrors = consoleErrorSpy.mock.calls.filter(([msg]) =>
      typeof msg === 'string' &&
      (msg.includes('style') || msg.includes('border') || msg.includes('Warning:'))
    );
    expect(styleErrors).toEqual([]);
  });

  it('stress-test: rapid in-flight state flips with click events during loading transitions', () => {
    const handleClick = vi.fn();

    function ClickableStateHarness() {
      const [loading, setLoading] = useState(false);
      const [variant, setVariant] = useState('primary');

      return (
        <Button
          variant={variant}
          isLoading={loading}
          onClick={() => {
            handleClick();
            setLoading(true);
            setVariant('secondary');
          }}
        >
          Action Button
        </Button>
      );
    }

    render(<ClickableStateHarness />);
    const btn = screen.getByRole('button', { name: /Action Button/i });

    // First click triggers handler and sets loading
    fireEvent.click(btn);
    expect(handleClick).toHaveBeenCalledTimes(1);
    expect(btn).toBeDisabled();

    // Subsequent click when disabled should not trigger handler
    fireEvent.click(btn);
    expect(handleClick).toHaveBeenCalledTimes(1);

    expect(consoleErrorSpy).not.toHaveBeenCalled();
  });

  it('verifies explicit DOM style invariants across all variants', () => {
    const variantExpectedBorders = [
      { variant: 'primary', expectedColor: 'transparent' },
      { variant: 'secondary', expectedColor: 'var(--border-default)' },
      { variant: 'outline', expectedColor: 'var(--border-default)' },
      { variant: 'danger', expectedColor: 'transparent' },
      { variant: 'ghost', expectedColor: 'transparent' },
      { variant: 'glass', expectedColor: 'var(--border-subtle)' },
    ];

    for (const item of variantExpectedBorders) {
      const { container, unmount } = render(
        <Button variant={item.variant}>Variant Test</Button>
      );
      const button = container.querySelector('button');

      expect(button.style.borderWidth).toBe('1px');
      expect(button.style.borderStyle).toBe('solid');
      expect(button.style.borderColor).toBe(item.expectedColor);

      unmount();
    }

    expect(consoleErrorSpy).not.toHaveBeenCalled();
  });

  it('handles edge cases: undefined style, null style, empty children without crashes', () => {
    const { rerender } = render(<Button style={undefined} />);
    expect(screen.getByRole('button')).toBeInTheDocument();

    rerender(<Button style={{}}>{null}</Button>);
    expect(screen.getByRole('button')).toBeInTheDocument();

    rerender(<Button leftIcon={<span data-testid="left-icon" />} rightIcon={<span data-testid="right-icon" />} />);
    expect(screen.getByTestId('left-icon')).toBeInTheDocument();
    expect(screen.getByTestId('right-icon')).toBeInTheDocument();

    // Switching to loading hides left/right icon and shows loader
    rerender(<Button isLoading leftIcon={<span data-testid="left-icon" />} rightIcon={<span data-testid="right-icon" />} />);
    expect(screen.queryByTestId('left-icon')).not.toBeInTheDocument();
    expect(screen.queryByTestId('right-icon')).not.toBeInTheDocument();

    expect(consoleErrorSpy).not.toHaveBeenCalled();
  });
});
