import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { ErrorState } from './index';

describe('ErrorState', () => {
  it('renders error message', () => {
    render(<ErrorState message="服务器错误，请稍后重试" onRetry={() => {}} />);
    expect(screen.getByText('服务器错误，请稍后重试')).toBeInTheDocument();
  });

  it('renders retry button', () => {
    render(<ErrorState message="请求超时" onRetry={() => {}} />);
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
  });

  it('calls onRetry when retry button is clicked', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<ErrorState message="请求失败" onRetry={onRetry} />);

    await user.click(screen.getByRole('button', { name: '重试' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('has alert role for accessibility', () => {
    render(<ErrorState message="错误" onRetry={() => {}} />);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
