import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { DetailPanel } from './index';

vi.mock('../../hooks/useKeywordTrend', () => ({
  useKeywordTrend: vi.fn(),
}));

vi.mock('../../hooks/useKeywordArticles', () => ({
  useKeywordArticles: vi.fn(),
}));

import { useKeywordTrend } from '../../hooks/useKeywordTrend';
import { useKeywordArticles } from '../../hooks/useKeywordArticles';

const mockUseKeywordTrend = vi.mocked(useKeywordTrend);
const mockUseKeywordArticles = vi.mocked(useKeywordArticles);

describe('DetailPanel', () => {
  beforeEach(() => {
    mockUseKeywordTrend.mockReturnValue({ data: null, loading: false, error: null });
    mockUseKeywordArticles.mockReturnValue({ data: null, loading: false, error: null });
  });

  it('shows placeholder message when no keyword is selected', () => {
    render(<DetailPanel keyword={null} group="domestic" />);
    expect(screen.getByText('请选择一个关键词查看详情')).toBeInTheDocument();
  });

  it('shows loading skeleton when trend data is loading', () => {
    mockUseKeywordTrend.mockReturnValue({ data: null, loading: true, error: null });
    mockUseKeywordArticles.mockReturnValue({ data: null, loading: false, error: null });

    render(<DetailPanel keyword="测试" group="domestic" />);
    expect(screen.getByLabelText('加载中')).toBeInTheDocument();
  });

  it('shows loading skeleton when articles data is loading', () => {
    mockUseKeywordTrend.mockReturnValue({ data: null, loading: false, error: null });
    mockUseKeywordArticles.mockReturnValue({ data: null, loading: true, error: null });

    render(<DetailPanel keyword="测试" group="domestic" />);
    expect(screen.getByLabelText('加载中')).toBeInTheDocument();
  });

  it('passes keyword and group to hooks', () => {
    render(<DetailPanel keyword="AI" group="international" />);
    expect(mockUseKeywordTrend).toHaveBeenCalledWith('AI', 'international');
    expect(mockUseKeywordArticles).toHaveBeenCalledWith('AI', 'international');
  });

  it('renders TrendChart and ArticleList when data is loaded', () => {
    mockUseKeywordTrend.mockReturnValue({
      data: [
        { timestamp: '2024-01-01T00:00:00Z', score: 5.0 },
        { timestamp: '2024-01-02T00:00:00Z', score: 7.0 },
        { timestamp: '2024-01-03T00:00:00Z', score: 6.5 },
      ],
      loading: false,
      error: null,
    });
    mockUseKeywordArticles.mockReturnValue({
      data: [
        { id: 1, title: '文章一', url: 'https://example.com/1', platform: 'ftchinese', section: '头条', date: '2024-01-03' },
      ],
      loading: false,
      error: null,
    });

    render(<DetailPanel keyword="经济" group="domestic" />);
    // TrendChart renders the keyword in its title
    expect(screen.getByText('「经济」趋势')).toBeInTheDocument();
    // ArticleList renders the article title
    expect(screen.getByText('文章一')).toBeInTheDocument();
  });
});
