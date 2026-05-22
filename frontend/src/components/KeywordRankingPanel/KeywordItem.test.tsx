import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { KeywordItem } from './KeywordItem';
import type { KeywordData } from '../../types';

function makeKeywordData(overrides: Partial<KeywordData> = {}): KeywordData {
  return {
    keyword: '人工智能',
    score: 8.75,
    rank: 1,
    count: 12,
    platform_count: 5,
    coverage: 0.625,
    sources: ['ftchinese', 'wsj', 'kr36', 'huxiu', 'zaobao'],
    sample_articles: [],
    trend_direction: 'rising',
    ...overrides,
  };
}

describe('KeywordItem', () => {
  it('renders rank, keyword, formatted score, and coverage', () => {
    const data = makeKeywordData();
    render(<KeywordItem data={data} isSelected={false} onClick={() => {}} />);

    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('人工智能')).toBeInTheDocument();
    expect(screen.getByText('8.8')).toBeInTheDocument();
    expect(screen.getByText('63%')).toBeInTheDocument();
  });

  it('displays rising trend indicator', () => {
    const data = makeKeywordData({ trend_direction: 'rising' });
    render(<KeywordItem data={data} isSelected={false} onClick={() => {}} />);

    expect(screen.getByText('↑')).toBeInTheDocument();
  });

  it('displays falling trend indicator', () => {
    const data = makeKeywordData({ trend_direction: 'falling' });
    render(<KeywordItem data={data} isSelected={false} onClick={() => {}} />);

    expect(screen.getByText('↓')).toBeInTheDocument();
  });

  it('displays stable trend indicator', () => {
    const data = makeKeywordData({ trend_direction: 'stable' });
    render(<KeywordItem data={data} isSelected={false} onClick={() => {}} />);

    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('displays stable indicator when trend_direction is undefined', () => {
    const data = makeKeywordData({ trend_direction: undefined });
    render(<KeywordItem data={data} isSelected={false} onClick={() => {}} />);

    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('applies selected styling when isSelected is true', () => {
    const data = makeKeywordData();
    const { container } = render(
      <KeywordItem data={data} isSelected={true} onClick={() => {}} />
    );

    const button = container.querySelector('.keyword-item');
    expect(button).toHaveClass('keyword-item--selected');
  });

  it('does not apply selected styling when isSelected is false', () => {
    const data = makeKeywordData();
    const { container } = render(
      <KeywordItem data={data} isSelected={false} onClick={() => {}} />
    );

    const button = container.querySelector('.keyword-item');
    expect(button).not.toHaveClass('keyword-item--selected');
  });

  it('calls onClick with keyword when clicked', async () => {
    const user = userEvent.setup();
    const handleClick = vi.fn();
    const data = makeKeywordData({ keyword: '经济增长' });

    render(<KeywordItem data={data} isSelected={false} onClick={handleClick} />);

    await user.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
    expect(handleClick).toHaveBeenCalledWith('经济增长');
  });

  it('has accessible aria-label with keyword details', () => {
    const data = makeKeywordData({ keyword: '科技', rank: 3, score: 6.5, coverage: 0.8, trend_direction: 'falling' });
    render(<KeywordItem data={data} isSelected={false} onClick={() => {}} />);

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-label', expect.stringContaining('科技'));
    expect(button).toHaveAttribute('aria-label', expect.stringContaining('排名 3'));
  });
});
