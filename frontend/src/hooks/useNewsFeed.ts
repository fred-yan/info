import { useState, useEffect, useRef } from 'react';
import { apiClient } from '../api/client';
import type { FeedFilters, NewsFeedResponse } from '../types';

interface UseNewsFeedResult {
  data: NewsFeedResponse | null;
  loading: boolean;
  error: string | null;
}

export function useNewsFeed(filters: FeedFilters, page: number): UseNewsFeedResult {
  const [data, setData] = useState<NewsFeedResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    setLoading(true);
    setError(null);

    const params: Record<string, string> = {
      page: String(page),
    };

    if (filters.platforms.length > 0) {
      params.platform = filters.platforms.join(',');
    }

    if (filters.section !== null) {
      params.section = filters.section;
    }

    apiClient
      .get<NewsFeedResponse>('/news/feed/', params)
      .then((result) => {
        if (!cancelledRef.current) {
          setData(result);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelledRef.current) {
          setError(err instanceof Error ? err.message : '未知错误');
          setData(null);
        }
      })
      .finally(() => {
        if (!cancelledRef.current) {
          setLoading(false);
        }
      });

    return () => {
      cancelledRef.current = true;
    };
  }, [filters.platforms.join(','), filters.section, page]);

  return { data, loading, error };
}
