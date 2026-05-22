import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TrendChart } from './index';
import type { TrendDataPoint } from '../../types';

describe('TrendChart', () => {
  it('renders empty state when data has fewer than 2 points', () => {
    const data: TrendDataPoint[] = [
      { timestamp: '2024-01-01T00:00:00Z', score: 5.0 },
    ];
    render(<TrendChart data={data} keyword="测试" />);
    expect(screen.getByText('数据不足，无法显示趋势图')).toBeInTheDocument();
  });

  it('renders empty state when data is empty', () => {
    render(<TrendChart data={[]} keyword="测试" />);
    expect(screen.getByText('数据不足，无法显示趋势图')).toBeInTheDocument();
  });

  it('renders chart when data has 2 or more points', () => {
    const data: TrendDataPoint[] = [
      { timestamp: '2024-01-01T00:00:00Z', score: 5.0 },
      { timestamp: '2024-01-02T00:00:00Z', score: 7.5 },
      { timestamp: '2024-01-03T00:00:00Z', score: 6.2 },
    ];
    render(<TrendChart data={data} keyword="人工智能" />);
    expect(screen.getByText('「人工智能」趋势')).toBeInTheDocument();
    expect(screen.queryByText('数据不足，无法显示趋势图')).not.toBeInTheDocument();
  });
});
