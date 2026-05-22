import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient, ApiError } from '../api/client';
import { mapHttpErrorToMessage } from '../utils/transformations';
import type { KeywordData, KeywordRankingResponse } from '../types';

interface UseKeywordRankingResult {
  data: KeywordData[] | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
}

/**
 * Fetches keyword ranking data for the given group.
 * Re-fetches when group changes; cancels in-flight requests on unmount or group change.
 */
export function useKeywordRanking(
  group: 'domestic' | 'international'
): UseKeywordRankingResult {
  const [data, setData] = useState<KeywordData[] | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [fetchTrigger, setFetchTrigger] = useState<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const retry = useCallback(() => {
    setFetchTrigger((prev) => prev + 1);
  }, []);

  useEffect(() => {
    // Cancel any previous in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let cancelled = false;

    setLoading(true);
    setError(null);
    setData(null);

    const fetchData = async () => {
      try {
        const response = await apiClient.get<KeywordRankingResponse>(
          '/keywords/ranking/',
          { group }
        );

        if (!cancelled && !controller.signal.aborted) {
          setData(response.keywords);
          setLoading(false);
        }
      } catch (err: unknown) {
        if (cancelled || controller.signal.aborted) {
          return;
        }

        if (err instanceof ApiError) {
          setError(mapHttpErrorToMessage(err.status));
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('未知错误');
        }
        setLoading(false);
      }
    };

    fetchData();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [group, fetchTrigger]);

  return { data, loading, error, retry };
}
