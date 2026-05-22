import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import type { ArticleDetail, ArticlesResponse } from '../types';

/**
 * Hook to fetch articles associated with a specific keyword.
 * Only fetches when keyword is non-null; returns null data otherwise.
 */
export function useKeywordArticles(keyword: string | null, group: string) {
  const [data, setData] = useState<ArticleDetail[] | null>(null);
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

    async function fetchArticles() {
      setLoading(true);
      setError(null);

      try {
        const response = await apiClient.get<ArticlesResponse>(
          '/keywords/articles/',
          { keyword: keyword!, group }
        );

        if (!cancelled) {
          setData(response.articles);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '未知错误');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchArticles();

    return () => {
      cancelled = true;
    };
  }, [keyword, group]);

  return { data, loading, error };
}
