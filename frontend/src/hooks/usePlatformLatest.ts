import { useState, useEffect, useCallback, useRef } from 'react';
import { apiClient, ApiError } from '../api/client';
import { mapHttpErrorToMessage } from '../utils/transformations';
import type { PlatformLatestResponse, UsePlatformLatestResult } from '../types';

/**
 * Fetches the latest batch of articles for a single platform,
 * grouped into cards by section / ranktime.
 * Re-fetches when platform changes; cancels in-flight requests on unmount.
 */
export function usePlatformLatest(platform: string): UsePlatformLatestResult {
  const [data, setData] = useState<PlatformLatestResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [fetchTrigger, setFetchTrigger] = useState<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  const retry = useCallback(() => {
    setFetchTrigger((prev) => prev + 1);
  }, []);

  useEffect(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;
    let cancelled = false;

    setLoading(true);
    setError(null);

    const fetchData = async () => {
      try {
        const response = await apiClient.get<PlatformLatestResponse>('/news/latest/', {
          platform,
        });

        if (!cancelled && !controller.signal.aborted) {
          setData(response);
          setLoading(false);
        }
      } catch (err: unknown) {
        if (cancelled || controller.signal.aborted) return;

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
  }, [platform, fetchTrigger]);

  return { data, loading, error, retry };
}
