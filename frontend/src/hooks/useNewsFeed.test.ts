import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useNewsFeed } from './useNewsFeed';
import type { FeedFilters, NewsFeedResponse } from '../types';

vi.mock('../api/client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

import { apiClient } from '../api/client';

const mockGet = apiClient.get as ReturnType<typeof vi.fn>;

describe('useNewsFeed', () => {
  const mockResponse: NewsFeedResponse = {
    articles: [
      { id: 1, title: 'Article 1', url: 'https://example.com/1', platform: 'apnews', section: 'world', date: '2024-01-01T00:00:00Z' },
      { id: 2, title: 'Article 2', url: 'https://example.com/2', platform: 'wsj', section: 'finance', date: '2024-01-02T00:00:00Z' },
    ],
    total: 50,
    page: 1,
    page_size: 20,
    has_next: true,
  };

  beforeEach(() => {
    mockGet.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should fetch articles with default filters and page', async () => {
    mockGet.mockResolvedValue(mockResponse);
    const filters: FeedFilters = { platforms: [], section: null };

    const { result } = renderHook(() => useNewsFeed(filters, 1));

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockResponse);
    expect(result.current.error).toBeNull();
    expect(mockGet).toHaveBeenCalledWith('/news/feed/', { page: '1' });
  });

  it('should include platform param as comma-separated string when platforms are selected', async () => {
    mockGet.mockResolvedValue(mockResponse);
    const filters: FeedFilters = { platforms: ['apnews', 'wsj'], section: null };

    const { result } = renderHook(() => useNewsFeed(filters, 1));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledWith('/news/feed/', {
      page: '1',
      platform: 'apnews,wsj',
    });
  });

  it('should include section param when section is non-null', async () => {
    mockGet.mockResolvedValue(mockResponse);
    const filters: FeedFilters = { platforms: [], section: 'world' };

    const { result } = renderHook(() => useNewsFeed(filters, 1));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledWith('/news/feed/', {
      page: '1',
      section: 'world',
    });
  });

  it('should include both platform and section params when both are set', async () => {
    mockGet.mockResolvedValue(mockResponse);
    const filters: FeedFilters = { platforms: ['economist'], section: 'tech' };

    const { result } = renderHook(() => useNewsFeed(filters, 2));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledWith('/news/feed/', {
      page: '2',
      platform: 'economist',
      section: 'tech',
    });
  });

  it('should set error state when API call fails', async () => {
    mockGet.mockRejectedValue(new Error('服务器错误，请稍后重试'));
    const filters: FeedFilters = { platforms: [], section: null };

    const { result } = renderHook(() => useNewsFeed(filters, 1));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('服务器错误，请稍后重试');
    expect(result.current.data).toBeNull();
  });

  it('should re-fetch when page changes', async () => {
    mockGet.mockResolvedValue(mockResponse);
    const filters: FeedFilters = { platforms: [], section: null };

    const { result, rerender } = renderHook(
      ({ filters, page }) => useNewsFeed(filters, page),
      { initialProps: { filters, page: 1 } }
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockGet).toHaveBeenCalledTimes(1);

    rerender({ filters, page: 2 });

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledTimes(2);
    });

    expect(mockGet).toHaveBeenLastCalledWith('/news/feed/', { page: '2' });
  });

  it('should re-fetch when filters change', async () => {
    mockGet.mockResolvedValue(mockResponse);
    const initialFilters: FeedFilters = { platforms: [], section: null };

    const { result, rerender } = renderHook(
      ({ filters, page }) => useNewsFeed(filters, page),
      { initialProps: { filters: initialFilters, page: 1 } }
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    const newFilters: FeedFilters = { platforms: ['apnews'], section: 'world' };
    rerender({ filters: newFilters, page: 1 });

    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledTimes(2);
    });

    expect(mockGet).toHaveBeenLastCalledWith('/news/feed/', {
      page: '1',
      platform: 'apnews',
      section: 'world',
    });
  });

  it('should handle non-Error rejection gracefully', async () => {
    mockGet.mockRejectedValue('string error');
    const filters: FeedFilters = { platforms: [], section: null };

    const { result } = renderHook(() => useNewsFeed(filters, 1));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('未知错误');
  });
});
