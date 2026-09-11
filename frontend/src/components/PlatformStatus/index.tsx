import { useState, useCallback, useEffect, useRef } from 'react';
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

type SheetState =
  | { status: 'closed' }
  | { status: 'loading' }
  | { status: 'selecting'; batches: BatchInfo[]; selectedBatch: string; timeout_seconds: number }
  | { status: 'running'; timeout_seconds: number; start_at: number; batch_id: string }
  | { status: 'done'; data: ExtractResult; batch_id: string }
  | { status: 'error'; message: string };

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatBatchId(bid: string): string {
  const raw = bid.startsWith('human_') ? bid.slice(6) : bid;
  const prefix = bid.startsWith('human_') ? '手动 ' : '';
  const m = raw.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})$/);
  if (!m) return bid;
  return `${prefix}${m[2]}-${m[3]} ${m[4]}:${m[5]}`;
}

// ── Bottom Sheet ─────────────────────────────────────────────────────────────

interface BottomSheetProps {
  platformName: string;
  platformLabel: string;
  onClose: () => void;
}

function BottomSheet({ platformName, platformLabel, onClose }: BottomSheetProps) {
  const [state, setState] = useState<SheetState>({ status: 'loading' });
  const overlayRef = useRef<HTMLDivElement>(null);

  // 加载批次列表
  useEffect(() => {
    let cancelled = false;
    apiClient.get<ExtractEstimate>('/llm/extract/', { platform: platformName })
      .then(est => {
        if (cancelled) return;
        const batches = est.available_batches ?? [];
        const defaultBatch = batches.length > 0 ? batches[0].batch_id : '';
        setState({
          status: 'selecting',
          batches,
          selectedBatch: defaultBatch,
          timeout_seconds: est.estimated_timeout_seconds,
        });
      })
      .catch(err => {
        if (cancelled) return;
        setState({ status: 'error', message: err instanceof Error ? err.message : '获取批次失败' });
      });
    return () => { cancelled = true; };
  }, [platformName]);

  // 点遮罩关闭
  const handleOverlayClick = useCallback((e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose();
  }, [onClose]);

  // ESC 关闭
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

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
      setState({ status: 'error', message: err instanceof Error ? err.message : '提取失败' });
    }
  }, [platformName]);

  return (
    <div className={styles.sheetOverlay} ref={overlayRef} onClick={handleOverlayClick} role="dialog" aria-modal="true" aria-label={`${platformLabel} 短语提取`}>
      <div className={styles.sheet}>
        {/* 拖拽把手 */}
        <div className={styles.sheetHandle} aria-hidden="true" />

        {/* 标题栏 */}
        <div className={styles.sheetHeader}>
          <span className={styles.sheetTitle}>{platformLabel} · 短语提取</span>
          <button type="button" className={styles.sheetClose} onClick={onClose} aria-label="关闭">✕</button>
        </div>

        {/* 内容区 */}
        <div className={styles.sheetBody}>
          {state.status === 'loading' && (
            <p className={styles.sheetHint}>加载批次列表…</p>
          )}

          {state.status === 'selecting' && (
            <>
              <p className={styles.sheetHint}>
                选择要提取的批次，已提取的批次标有 ✓
              </p>
              <div className={styles.batchList}>
                {state.batches.length === 0 ? (
                  <p className={styles.sheetEmpty}>暂无历史批次，将使用最新数据</p>
                ) : (
                  state.batches.map(b => (
                    <label
                      key={b.batch_id}
                      className={`${styles.batchItem} ${state.selectedBatch === b.batch_id ? styles.batchItemSelected : ''}`}
                    >
                      <input
                        type="radio"
                        name="batch"
                        value={b.batch_id}
                        checked={state.selectedBatch === b.batch_id}
                        onChange={() => setState({ ...state, selectedBatch: b.batch_id })}
                        className={styles.batchRadio}
                      />
                      <span className={styles.batchItemContent}>
                        <span className={styles.batchItemTime}>{formatBatchId(b.batch_id)}</span>
                        <span className={styles.batchItemMeta}>
                          {b.article_count} 条文章
                          {b.extracted && <span className={styles.batchExtractedTag}>已提取</span>}
                        </span>
                      </span>
                    </label>
                  ))
                )}
              </div>
              <div className={styles.sheetActions}>
                <button
                  type="button"
                  className={styles.sheetActionBtn}
                  onClick={() => handleExtract(state.selectedBatch, state.timeout_seconds)}
                >
                  开始提取
                </button>
                <button type="button" className={styles.sheetCancelBtn} onClick={onClose}>取消</button>
              </div>
            </>
          )}

          {state.status === 'running' && (() => {
            const elapsed = Math.round((Date.now() - state.start_at) / 1000);
            return (
              <div className={styles.sheetRunning}>
                <div className={styles.sheetSpinner} aria-hidden="true" />
                <p className={styles.sheetRunningText}>
                  正在提取 <strong>{formatBatchId(state.batch_id)}</strong> 批次的短语…
                </p>
                <p className={styles.sheetRunningMeta}>
                  已用时 {elapsed}s，预计 ≤{state.timeout_seconds}s
                </p>
              </div>
            );
          })()}

          {state.status === 'done' && (
            <div className={styles.sheetDone}>
              <div className={styles.sheetDoneIcon} aria-hidden="true">✓</div>
              <p className={styles.sheetDoneTitle}>提取完成</p>
              <p className={styles.sheetDoneMeta}>
                批次：{formatBatchId(state.batch_id)}
                &nbsp;·&nbsp;{state.data.article_count} 条
                &nbsp;·&nbsp;{state.data.elapsed_seconds}s
                {state.data.skipped_by_cache && <span className={styles.batchExtractedTag}>缓存</span>}
              </p>
              <button type="button" className={styles.sheetCancelBtn} onClick={onClose}>关闭</button>
            </div>
          )}

          {state.status === 'error' && (
            <div className={styles.sheetError}>
              <p className={styles.sheetErrorText}>{state.message}</p>
              <button type="button" className={styles.sheetCancelBtn} onClick={onClose}>关闭</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Extract button (table cell) ──────────────────────────────────────────────

function ExtractCell({ platformName, platformLabel }: { platformName: string; platformLabel: string }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button type="button" className={styles.extractBtn} onClick={() => setOpen(true)}>
        提取短语
      </button>
      {open && (
        <BottomSheet
          platformName={platformName}
          platformLabel={platformLabel}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

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
                  <ExtractCell platformName={platform.name} platformLabel={platform.label} />
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
