import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { EmptyState } from './index';

describe('EmptyState', () => {
  it('renders the provided message', () => {
    render(<EmptyState message="暂无数据" />);
    expect(screen.getByText('暂无数据')).toBeInTheDocument();
  });

  it('renders with custom message', () => {
    render(<EmptyState message="请选择一个关键词查看详情" />);
    expect(screen.getByText('请选择一个关键词查看详情')).toBeInTheDocument();
  });

  it('has status role for accessibility', () => {
    render(<EmptyState message="暂无数据" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});
