import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { Pagination } from './index';

describe('Pagination', () => {
  it('renders previous button, current page, and next button', () => {
    render(<Pagination page={2} hasNext={true} onPageChange={() => {}} />);

    expect(screen.getByRole('button', { name: '上一页' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '下一页' })).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('disables previous button on page 1', () => {
    render(<Pagination page={1} hasNext={true} onPageChange={() => {}} />);

    expect(screen.getByRole('button', { name: '上一页' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '下一页' })).toBeEnabled();
  });

  it('disables next button when hasNext is false', () => {
    render(<Pagination page={3} hasNext={false} onPageChange={() => {}} />);

    expect(screen.getByRole('button', { name: '上一页' })).toBeEnabled();
    expect(screen.getByRole('button', { name: '下一页' })).toBeDisabled();
  });

  it('calls onPageChange with page - 1 when previous is clicked', async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Pagination page={3} hasNext={true} onPageChange={onPageChange} />);

    await user.click(screen.getByRole('button', { name: '上一页' }));

    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('calls onPageChange with page + 1 when next is clicked', async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Pagination page={2} hasNext={true} onPageChange={onPageChange} />);

    await user.click(screen.getByRole('button', { name: '下一页' }));

    expect(onPageChange).toHaveBeenCalledWith(3);
  });

  it('does not call onPageChange when disabled previous is clicked', async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Pagination page={1} hasNext={true} onPageChange={onPageChange} />);

    await user.click(screen.getByRole('button', { name: '上一页' }));

    expect(onPageChange).not.toHaveBeenCalled();
  });

  it('does not call onPageChange when disabled next is clicked', async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    render(<Pagination page={1} hasNext={false} onPageChange={onPageChange} />);

    await user.click(screen.getByRole('button', { name: '下一页' }));

    expect(onPageChange).not.toHaveBeenCalled();
  });
});
