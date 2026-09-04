import { useState, useEffect, useRef, useCallback } from 'react';
import { apiClient, ApiError } from '../api/client';
import { mapHttpErrorToMessage } from '../utils/transformations';
import type { ArticleCard, PlatformLatestResponse, PlatformMetadata } from '../types';

export interface PlatformError {
  platform: string;
  label: string;
  message: string;
}

interface UseGroupCardsResult {
  cards: ArticleCard[];
  loadingPlatforms: string[];
  platformErrors: PlatformError[];
  retry: () => void;
  refreshPlatform: (platform: string) => void;
}

/**
 * Fetches news/latest/ for every platform in the given list in parallel.
 * Uses a single shared resultMap (ref) so full-reload and per-platform refresh
 * both write to the same store — preventing other platforms from going blank.
 */
export function useGroupCards(platforms: PlatformMetadata[]): UseGroupCardsResult {
  const [cards, setCards] = useState<ArticleCard[]>([]);
  const [loadingPlatforms, setLoadingPlatforms] = useState<string[]>([]);
  const [platformErrors, setPlatformErrors] = useState<PlatformError[]>([]);
  const [fetchTrigger, setFetchTrigger] = useState(0);
  const [platformTriggers, setPlatformTriggers] = useState<Record<string, number>>({});

  // Shared result store — survives re-renders and is used by BOTH effects
  const resultMapRef = useRef<Map<string, ArticleCard[]>>(new Map());
  const errorMapRef = useRef<Map<string, PlatformError>>(new Map());
  const prevTriggersRef = useRef<Record<string, number>>({});
  const abortRef = useRef<AbortController | null>(null);

  const retry = useCallback(() => setFetchTrigger((n) => n + 1), []);

  const refreshPlatform = useCallback((platform: string) => {
    setPlatformTriggers((prev) => ({ ...prev, [platform]: (prev[platform] ?? 0) + 1 }));
  }, []);

  // Rebuild displayed cards from the shared ref in platform order
  const rebuildCards = useCallback((names: string[]) => {
    setCards(names.flatMap((n) => resultMapRef.current.get(n) ?? []));
    setPlatformErrors(names.flatMap((n) => {
      const e = errorMapRef.current.get(n);
      return e ? [e] : [];
    }));
  }, []);

  const fetchOnePlatform = useCallback(
    async (
      platform: string,
      meta: PlatformMetadata | undefined,
      names: string[],
      signal?: AbortSignal,
    ) => {
      try {
        const resp = await apiClient.get<PlatformLatestResponse>('/news/latest/', { platform });
        if (signal?.aborted) return;

        const interval = meta?.update_interval;
        const newCards = interval
          ? resp.cards.map((c) => ({ ...c, update_interval: interval }))
          : resp.cards;
        resultMapRef.current.set(platform, newCards);
        errorMapRef.current.delete(platform);
      } catch (err) {
        if (signal?.aborted) return;
        if (err instanceof ApiError && err.status === 404) {
          resultMapRef.current.set(platform, []);
          errorMapRef.current.delete(platform);
        } else {
          const message = err instanceof ApiError
            ? mapHttpErrorToMessage(err.status)
            : '加载失败';
          errorMapRef.current.set(platform, {
            platform,
            label: meta?.label ?? platform,
            message,
          });
        }
      } finally {
        if (!signal?.aborted) {
          setLoadingPlatforms((prev) => prev.filter((n) => n !== platform));
          rebuildCards(names);
        }
      }
    },
    [rebuildCards],
  );

  // ── Full reload (group change or retry) ──────────────────────────────────
  useEffect(() => {
    if (platforms.length === 0) {
      setCards([]);
      setLoadingPlatforms([]);
      setPlatformErrors([]);
      resultMapRef.current.clear();
      errorMapRef.current.clear();
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const platformMap = new Map(platforms.map((p) => [p.name, p]));
    const names = platforms.map((p) => p.name);

    // Reset shared store for fresh load
    resultMapRef.current.clear();
    errorMapRef.current.clear();

    setLoadingPlatforms([...names]);
    setPlatformErrors([]);
    setCards([]);

    names.forEach((name) =>
      fetchOnePlatform(name, platformMap.get(name), names, controller.signal)
    );

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platforms.map((p) => p.name).join(','), fetchTrigger]);

  // ── Per-platform refresh ──────────────────────────────────────────────────
  useEffect(() => {
    const prev = prevTriggersRef.current;
    const changed = Object.entries(platformTriggers).filter(
      ([p, t]) => (prev[p] ?? 0) !== t,
    );
    prevTriggersRef.current = { ...platformTriggers };

    if (changed.length === 0) return;

    const names = platforms.map((p) => p.name);

    changed.forEach(([platform]) => {
      const meta = platforms.find((p) => p.name === platform);
      setLoadingPlatforms((prev) =>
        prev.includes(platform) ? prev : [...prev, platform],
      );
      fetchOnePlatform(platform, meta, names);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platformTriggers]);

  return { cards, loadingPlatforms, platformErrors, retry, refreshPlatform };
}
