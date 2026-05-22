import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { ArticleList } from './index';
import type { ArticleDetail } from '../../types';

const mockArticles: ArticleDetail[] = [
  {
    id: 1,
    title: '文章标题一',
    url: 'https://example.com/article1',
    platform: 'ftchinese',
    section: '科技',
    date: '2024-01-15T10:00:00Z',
  },
  {
    id: 2,
    title: '文章标题二',
    url: 'https://example.com/article2',
    platform: 'ftchinese',
    section: '财经',
    date: '2024-01-14T08:00:00Z',
  },
  {
    id: 3,
    title: '文章标题三',
    url: 'https://example.com/article3',
    platform: 'kr36',
    section: '创投',
    date: '2024-01-13T12:00:00Z',
  },
];

describe('ArticleList', () => {
  it('renders EmptyState when articles array is empty', () => {
    render(<ArticleList articles={[]} />);
    expect(screen.getByText('暂无相关文章')).toBeInTheDocument();
  });

  it('renders platform group headers with article count', () => {
    render(<ArticleList articles={mockArticles} />);
    const allFtchinese = screen.getAllByText('ftchinese');
    // One in group header + two in article meta labels
    expect(allFtchinese.length).toBe(3);
    expect(screen.getByText('(2)')).toBeInTheDocument();
    const allKr36 = screen.getAllByText('kr36');
    // One in group header + one in article meta label
    expect(allKr36.length).toBe(2);
    expect(screen.getByText('(1)')).toBeInTheDocument();
  });

  it('renders article titles as links opening in new tab', () => {
    render(<ArticleList articles={mockArticles} />);
    const link = screen.getByText('文章标题一');
    expect(link.tagName).toBe('A');
    expect(link).toHaveAttribute('href', 'https://example.com/article1');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('renders platform label and formatted date for each article', () => {
    render(<ArticleList articles={mockArticles} />);
    expect(screen.getByText('2024-01-15')).toBeInTheDocument();
    expect(screen.getByText('2024-01-14')).toBeInTheDocument();
    expect(screen.getByText('2024-01-13')).toBeInTheDocument();
  });

  it('groups articles by platform sorted by count descending', () => {
    render(<ArticleList articles={mockArticles} />);
    const headers = screen.getAllByText(/ftchinese|kr36/);
    // ftchinese has 2 articles, kr36 has 1 — ftchinese should appear first
    expect(headers[0].textContent).toBe('ftchinese');
  });
});
