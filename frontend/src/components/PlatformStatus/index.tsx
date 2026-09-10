import { useState, useCallback } from 'react';
import { usePlatforms } from '../../hooks/usePlatforms';
import { isStale } from '../../utils/transformations';
import { apiClient } from '../../api/client';
import { LoadingSkeleton } from '../LoadingSkeleton';
import styles from './PlatformStatus.module.css';

// ── Types ────────────────────────────────────────────────────────────────────

interface BatchInfo {
  batch_id: string;
  fetch_time: string;
  article_count: number;
  extracted: boolean;
}

interface ExtractEstimate {
  article_count: number;
  estimated_timeout_seconds: number;
  available_batches: BatchInfo[];
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
  | { status: 'loading_batches' }
  | { status: 'selecting'; batches: BatchInfo[]; selectedBatch: string; timeout_seconds: number }
  | { status: 'running'; timeout_seconds: number; start_at: number; batch_id: string }
  | { status: 'done'; data: ExtractResult; batch_id: string }
  | { status: 'error'; message: string };

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBatchId(bid: string): string {
  // "20260910_1800" → "09-10 18:00"  |  "human_20260910_1835" → "手动 09-10 18:35"
  const raw = bid.startsWith('human_') ? bid.slice(6) : bid;
  const prefix = bid.startsWith('human_') ? '手动 ' : '';
  const m = raw.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})$/);
  if (!m) return bid;
  return `${prefix}${m[2]}-${m[3]} ${m[4]}:${m[5]}`;
}

// ── Extract button + batch selector ─────────────────────────────────────────

function ExtractCell({ platformName }: { platformName: string }) {
  const [state, setState] = useState<ExtractState>({ status: 'idle' });

  // Step 1: load available batches
  const handleOpenSelector = useCallback(async () => {
    setState({ status: 'loading_batches' });
    try {
      const est = await apiClient.get<ExtractEstimate>('/llm/extract/', {
        platform: platformName,
      });
      if (est.article_count === 0 && est.available_batches.length === 0) {
        setState({ status: 'error', message: '该平台暂无文章数据' });
        return;
      }
      const batches = est.available_batches ?? [];
      // 默认选最新批次
      const defaultBatch = batches.length > 0 ? batches[0].batch_id : '';
      setState({
        status: 'selecting',
        batches,
        selectedBatch: defaultBatch,
        timeout_seconds: est.estimated_timeout_seconds,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '获取批次失败';
      setState({ status: 'error', message: msg });
    }
  }, [platformName]);

  // Step 2: run extraction for selected batch
  const handleExtract = useCallback(async (batchId: string, timeoutSecs: number) => {
    setState({ status: 'running', timeout_seconds: timeoutSecs, start_at: Date.now(), batch_id: batchId });
    try {
      const result = await apiClient.post<ExtractResult>('/llm/extract/', {
        platform: platformName,
        force: false,
        batch_id: batchId || undefined,
      });
      setState({ status: 'done', data: result, batch_id: batchId });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '提取失败';
      setState({ status: 'error', message: msg });
    }
  }, [platformName]);

  const handleReset = useCallback(() => setState({ status: 'idle' }), []);

  // ── idle ──
  if (state.status === 'idle') {
    return (
      <button type="button" className={styles.extractBtn} onClick={handleOpenSelector}>
        提取短语
      </button>
    );
  }

  // ── loading batches ──
  if (state.status === 'loading_batches') {
    return <span className={styles.extractStatus}>加载批次…</span>;
  }

  // ── selecting batch ──
  if (state.status === 'selecting') {
    const { batches, selectedBatch, timeout_seconds } = state;
    return (
      <span className={styles.extractSelector}>
        <select
          className={styles.batchSelect}
          value={selectedBatch}
          onChange={e => setState({ ...state, selectedBatch: e.target.value })}
          aria-label="选择批次"
        >
          {batches.length === 0 && (
            <option value="">（无历史批次）</option>
          )}
          {batches.map(b => (
            <option key={b.batch_id} value={b.batch_id}>
              {formatBatchId(b.batch_id)}
              {' '}({b.article_count}条{b.extracted ? ' ✓' : ''})
            </option>
          ))}
        </select>
        <button
          type="button"
          className={styles.extractBtn}
          onClick={() => handleExtract(selectedBatch, timeout_seconds)}
          disabled={!selectedBatch && batches.length > 0}
        >
          执行
        </button>
        <button type="button" className={styles.extractResetBtn} onClick={handleReset}>
          取消
        </button>
      </span>
    );
  }

  // ── running ──
  if (state.status === 'running') {
    const elapsed = Math.round((Date.now() - state.start_at) / 1000);
    return (
      <span className={styles.extractStatus}>
        提取中… {elapsed}s / 预计≤{state.timeout_seconds}s
        {state.batch_id && <span className={styles.batchTag}>{formatBatchId(state.batch_id)}</span>}
      </span>
    );
  }

  // ── error ──
  if (state.status === 'error') {
    return (
      <span className={styles.extractError} title={state.message}>
        失败
        <button type="button" className={styles.extractResetBtn} onClick={handleReset}>重试</button>
      </span>
    );
  }

  // ── done ──
  const { data, batch_id } = state;
  return (
    <span className={styles.extractDone}>
      完成 {data.article_count}条/{data.elapsed_seconds}s
      {data.skipped_by_cache && ' (缓存)'}
      {batch_id && <span className={styles.batchTag}>{formatBatchId(batch_id)}</span>}
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
