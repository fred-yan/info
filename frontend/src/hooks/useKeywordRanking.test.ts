import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useKeywordRanking } from './useKeywordRanking';

const mockKeywords = [
  {
    keyword: 'AI',
    score: 95.5,
    rank: 1,
    count: 12,
    platform_count: 5,
    coverage: 0.8,
    sources: ['wsj', 'economist'],
    sample_articles: [],
    trend_direction: 'rising' as const,
  },
  {
    keyword: '经济',
    score: 80.2,
    rank: 2,
    count: 8,
    platform_count: 4,
    coverage: 0.6,
    sources: ['ftchinese'],
    sample_articles: [],
    trend_direction: 'stable' as const,
  },
];

describe('useKeywordRanking', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should start with loading=true, data=null, error=null', () => {
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(() => {}) // never resolves
    );

    const { result } = renderHook(() => useKeywordRanking('domestic'));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('should set data on successful fetch', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          analysis_time: '2024-01-01T00:00:00Z',
          group: 'domestic',
          keywords: mockKeywords,
        }),
    });

    const { result } = renderHook(() => useKeywordRanking('domestic'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockKeywords);
    expect(result.current.error).toBeNull();
  });

  it('should pass group as query parameter', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          analysis_time: '2024-01-01T00:00:00Z',
          group: 'international',
          keywords: [],
        }),
    });

    renderHook(() => useKeywordRanking('international'));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalled();
    });

    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('group=international');
  });

  it('should set error message on API error', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve('Internal Server Error'),
    });

    const { result } = renderHook(() => useKeywordRanking('domestic'));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('服务器错误，请稍后重试');
    expect(result.current.data).toBeNull();
  });

  it('should re-fetch when group changes', async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          analysis_time: '2024-01-01T00:00:00Z',
          group: 'domestic',
          keywords: mockKeywords,
        }),
    });

    const { result, rerender } = renderHook(
      ({ group }: { group: 'domestic' | 'international' }) => useKeywordRanking(group),
      { initialProps: { group: 'domestic' as 'domestic' | 'international' } }
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Change group
    rerender({ group: 'international' as const });

    // Should be loading again
    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // fetch should have been called twice
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('should retry fetch when retry() is called', async () => {
    let callCount = 0;
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({
          ok: false,
          status: 503,
          text: () => Promise.resolve('Service Unavailable'),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            analysis_time: '2024-01-01T00:00:00Z',
            group: 'domestic',
            keywords: mockKeywords,
          }),
      });
    });

    const { result } = renderHook(() => useKeywordRanking('domestic'));

    // Wait for first (failed) fetch
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBeTruthy();

    // Retry
    act(() => {
      result.current.retry();
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(mockKeywords);
    expect(result.current.error).toBeNull();
  });

  it('should not update state after unmount', async () => {
    let resolvePromise: (value: unknown) => void;
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePromise = resolve;
        })
    );

    const { result, unmount } = renderHook(() => useKeywordRanking('domestic'));

    expect(result.current.loading).toBe(true);

    // Unmount before fetch resolves
    unmount();

    // Resolve the fetch after unmount
    resolvePromise!({
      ok: true,
      json: () =>
        Promise.resolve({
          analysis_time: '2024-01-01T00:00:00Z',
          group: 'domestic',
          keywords: mockKeywords,
        }),
    });

    // State should remain as loading since component unmounted
    // No error should be thrown (no state update on unmounted component)
  });
});
