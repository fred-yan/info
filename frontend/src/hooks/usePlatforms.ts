import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api/client';
import type { PlatformMetadata } from '../types';

interface PlatformsResponse {
  platforms: PlatformMetadata[];
}

interface UsePlatformsResult {
  data: PlatformMetadata[] | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
}

export function usePlatforms(): UsePlatformsResult {
  const [data, setData] = useState<PlatformMetadata[] | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [fetchTrigger, setFetchTrigger] = useState<number>(0);

  const retry = useCallback(() => {
    setFetchTrigger((prev) => prev + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function fetchPlatforms() {
      setLoading(true);
      setError(null);

      try {
        const response = await apiClient.get<PlatformsResponse>('/platforms/');
        if (!cancelled) {
          setData(response.platforms);
          setLoading(false);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '未知错误');
          setLoading(false);
        }
      }
    }

    fetchPlatforms();

    return () => {
      cancelled = true;
    };
  }, [fetchTrigger]);

  return { data, loading, error, retry };
}
