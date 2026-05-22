import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { LoadingSkeleton } from './index';

describe('LoadingSkeleton', () => {
  it('renders with default 5 rows', () => {
    const { container } = render(<LoadingSkeleton />);
    const bars = container.querySelectorAll('[class*="bar"]');
    // 5 bars (each has "bar" + a size class)
    expect(bars.length).toBe(5);
  });

  it('renders with custom row count', () => {
    const { container } = render(<LoadingSkeleton rows={3} />);
    const bars = container.querySelectorAll('[class*="bar"]');
    expect(bars.length).toBe(3);
  });

  it('has accessible status role', () => {
    render(<LoadingSkeleton />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('has aria-label for screen readers', () => {
    render(<LoadingSkeleton />);
    expect(screen.getByLabelText('加载中')).toBeInTheDocument();
  });
});
