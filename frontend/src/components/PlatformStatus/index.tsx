import { useState, useCallback } from 'react';
import { usePlatforms } from '../../hooks/usePlatforms';
import { isStale } from '../../utils/transformations';
import { apiClient } from '../../api/client';
import { LoadingSkeleton } from '../LoadingSkeleton';
import styles from './PlatformStatus.module.css';

// ── Types ────────────────────────────────────────────────────────────────────

interface ExtractEstimate {
  article_count: number;
  estimated_timeout_seconds: number;
}

interface ExtractResult {
  article_count: number;
  elapsed_seconds: number;
  skipped_by_cache: boolean;
  results: Array<{
    article_id: number;
    title: string;
    extracted_phrases: string[];
    normalized_phrases: string[];
  }>;
  error?: string;
}

type ExtractState =
  | { status: 'idle' }
  | { status: 'estimating' }
  | { status: 'running'; timeout_seconds: number; start_at: number }
  | { status: 'done'; data: ExtractResult }
  | { status: 'error'; message: string };

// ── Extract button + result panel ────────────────────────────────────────────

function ExtractCell({ platformName }: { platformName: string }) {
  const [state, setState] = useState<ExtractState>({ status: 'idle' });

  const handleExtract = useCallback(async () => {
    setState({ status: 'estimating' });

    // Step 1: GET estimate
    try {
      const est = await apiClient.get<ExtractEstimate>('/llm/extract/', {
        platform: platformName,
      });

      if (est.article_count === 0) {
        setState({ status: 'error', message: '该平台暂无文章数据' });
        return;
      }

      setState({ status: 'running', timeout_seconds: est.estimated_timeout_seconds, start_at: Date.now() });

      // Step 2: POST extract
      const result = await apiClient.post<ExtractResult>('/llm/extract/', {
        platform: platformName,
        force: false,
      });

      setState({ status: 'done', data: result });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '提取失败';
      setState({ status: 'error', message: msg });
    }
  }, [platformName]);

  const handleReset = useCallback(() => setState({ status: 'idle' }), []);

  if (state.status === 'idle') {
    return (
      <button type="button" className={styles.extractBtn} onClick={handleExtract}>
        提取短语
      </button>
    );
  }

  if (state.status === 'estimating') {
    return <span className={styles.extractStatus}>估算中…</span>;
  }

  if (state.status === 'running') {
    const elapsed = Math.round((Date.now() - state.start_at) / 1000);
    return (
      <span className={styles.extractStatus}>
        提取中… {elapsed}s / 预计≤{state.timeout_seconds}s
      </span>
    );
  }

  if (state.status === 'error') {
    return (
      <span className={styles.extractError} title={state.message}>
        失败
        <button type="button" className={styles.extractResetBtn} onClick={handleReset}>重试</button>
      </span>
    );
  }

  // done
  const { data } = state;
  return (
    <span className={styles.extractDone}>
      完成 {data.article_count}条/{data.elapsed_seconds}s
      {data.skipped_by_cache && ' (缓存)'}
      <button type="button" className={styles.extractResetBtn} onClick={handleReset}>
        重置
      </button>
    </span>
  );
}

// ── Result drawer — shown below the table ────────────────────────────────────

// ── Main component ────────────────────────────────────────────────────────────

export default function PlatformStatus() {
  const { data: platforms, loading, error } = usePlatforms();

  if (loading) {
    return (
      <div className={styles.container}>
        <h1 className={styles.title}>平台状态</h1>
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <h1 className={styles.title}>平台状态</h1>
        <div className={styles.error} role="alert"><p>{error}</p></div>
      </div>
    );
  }

  if (!platforms || platforms.length === 0) {
    return (
      <div className={styles.container}>
        <h1 className={styles.title}>平台状态</h1>
        <p className={styles.empty}>暂无平台数据</p>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>平台状态</h1>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>平台</th>
            <th>分组</th>
            <th>最后抓取时间</th>
            <th>文章数</th>
            <th>状态</th>
            <th>短语提取</th>
          </tr>
        </thead>
        <tbody>
          {platforms.map((platform) => {
            const stale = isStale(platform.last_fetch);
            return (
              <tr key={platform.name} className={stale ? styles.staleRow : ''}>
                <td className={styles.labelCell}>{platform.label}</td>
                <td>
                  <span className={platform.group === 'domestic' ? styles.groupDomestic : styles.groupInternational}>
                    {platform.group === 'domestic' ? '国内' : '国际'}
                  </span>
                </td>
                <td className={styles.timestampCell}>
                  {formatTimestamp(platform.last_fetch)}
                </td>
                <td className={styles.countCell}>{platform.article_count}</td>
                <td>
                  {stale ? (
                    <span className={styles.staleIndicator} title="数据可能过期">
                      <span className={styles.staleDot} aria-hidden="true" />
                      数据可能过期
                    </span>
                  ) : (
                    <span className={styles.freshIndicator}>正常</span>
                  )}
                </td>
                <td>
                  <ExtractCell platformName={platform.name} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return isoString;
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}
