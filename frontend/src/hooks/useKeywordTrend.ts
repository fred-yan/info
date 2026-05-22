import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import type { TrendDataPoint, TrendResponse } from '../types';

interface UseKeywordTrendResult {
  data: TrendDataPoint[] | null;
  loading: boolean;
  error: string | null;
}

export function useKeywordTrend(keyword: string | null, group: string): UseKeywordTrendResult {
  const [data, setData] = useState<TrendDataPoint[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!keyword) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    apiClient
      .get<TrendResponse>('/keywords/trend/', {
        keyword,
        group,
        days: '7',
      })
      .then((response) => {
        if (!cancelled) {
          setData(response.data_points);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '未知错误');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [keyword, group]);

  return { data, loading, error };
}
