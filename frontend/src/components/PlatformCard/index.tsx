import { useState, useCallback, useEffect } from 'react';
import { usePlatformLatest } from '../../hooks/usePlatformLatest';
import { apiClient } from '../../api/client';
import type { LatestArticle, ArticleCard } from '../../types';
import styles from './PlatformCard.module.css';

// ── Time formatting ───────────────────────────────────────────────────────────

function formatLocalTime(isoString: string): string {
  const d = new Date(isoString); // +00:00 suffix ensures correct UTC parsing
  if (isNaN(d.getTime())) return '';
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

// ── Refresh icon ──────────────────────────────────────────────────────────────

function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      width="13" height="13" viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth="2.2"
      strokeLinecap="round" strokeLinejoin="round"
      className={spinning ? styles.spinning : undefined}
      aria-hidden="true"
    >
      <path d="M23 4v6h-6" />
      <path d="M1 20v-6h6" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10" />
      <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14" />
    </svg>
  );
}

// ── Article row — with phrase tooltip on index click ─────────────────────────

interface ArticlePhrases {
  extracted_phrases: string[];
  normalized_phrases: string[];
}

function ArticleRow({ article }: { article: LatestArticle }) {
  const isTop = article.index <= 3;
  const [phrases, setPhrases] = useState<ArticlePhrases | null>(null);
  const [loadingPhrases, setLoadingPhrases] = useState(false);
  const [showPhrases, setShowPhrases] = useState(false);

  const handleIndexClick = useCallback(async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (showPhrases) {
      setShowPhrases(false);
      return;
    }

    if (phrases) {
      setShowPhrases(true);
      return;
    }

    if (!article.id) return;

    setLoadingPhrases(true);
    try {
      const data = await apiClient.get<ArticlePhrases>('/llm/phrases/', {
        article_id: String(article.id),
      });
      setPhrases(data);
      setShowPhrases(true);
    } catch {
      setPhrases({ extracted_phrases: [], normalized_phrases: [] });
      setShowPhrases(true);
    } finally {
      setLoadingPhrases(false);
    }
  }, [article.id, phrases, showPhrases]);

  const allPhrases = phrases
    ? phrases.normalized_phrases
    : [];

  return (
    <div style={{ position: 'relative' }}>
      <a
        href={article.url}
        target="_blank"
        rel="noopener noreferrer"
        title={article.title}
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '0.45rem',
          padding: '0.42rem 0.75rem',
          textDecoration: 'none',
          color: 'inherit',
        }}
      >
        {/* Clickable index */}
        <span
          onClick={handleIndexClick}
          title={showPhrases ? '收起短语' : '查看关键短语'}
          style={{
            flexShrink: 0,
            width: '1.3rem',
            textAlign: 'right',
            fontSize: '0.78rem',
            fontWeight: 700,
            color: isTop ? 'var(--rank-top, #2563eb)' : 'var(--text-muted, #9ca3af)',
            lineHeight: 1.45,
            paddingTop: '0.02rem',
            cursor: 'pointer',
            userSelect: 'none',
            opacity: loadingPhrases ? 0.5 : 1,
          }}
        >
          {loadingPhrases ? '…' : article.index}
        </span>
        <span style={{
          flex: 1,
          minWidth: 0,
          fontSize: '0.85rem',
          lineHeight: 1.45,
          color: 'var(--text, #374151)',
          wordBreak: 'normal',
          overflowWrap: 'break-word',
        }}>
          {article.title}
        </span>
      </a>

      {/* Phrase tags — inline below the title */}
      {showPhrases && (
        <div style={{
          padding: '0 0.75rem 0.45rem 2.2rem',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.3rem',
        }}>
          {allPhrases.length === 0 ? (
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted, #9ca3af)' }}>
              暂无短语数据
            </span>
          ) : (
            allPhrases.map((p) => (
              <span
                key={p}
                style={{
                  fontSize: '0.72rem',
                  padding: '0.1rem 0.45rem',
                  borderRadius: '3px',
                  background: 'var(--accent-bg, rgba(37,99,235,0.1))',
                  color: 'var(--accent, #2563eb)',
                  border: '1px solid var(--accent-bg, rgba(37,99,235,0.2))',
                  whiteSpace: 'nowrap',
                }}
              >
                {p}
              </span>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ── Skeleton card ─────────────────────────────────────────────────────────────

const SKELETON_WIDTHS = ['82%', '70%', '88%', '65%', '78%', '72%', '85%', '60%'];

export function PlatformCardSkeleton({ title }: { title?: string }) {
  return (
    <article className={styles.card} aria-busy="true">
      <header className={styles.header}>
        <div className={styles.headerTop}>
          <div className={styles.headerLeft}>
            <span className={`${styles.statusDot} ${styles.statusDotStale}`} aria-hidden="true" />
            <span className={styles.cardTitle}>{title ?? '加载中…'}</span>
          </div>
        </div>
      </header>
      <div className={styles.body}>
        <div className={styles.skeleton}>
          {SKELETON_WIDTHS.map((w, i) => (
            <div key={i} className={styles.skeletonLine} style={{ width: w }} />
          ))}
        </div>
      </div>
    </article>
  );
}

// ── Error card ────────────────────────────────────────────────────────────────

export function PlatformCardError({ title, onRetry }: { title?: string; onRetry: () => void }) {
  return (
    <article className={styles.card}>
      <header className={styles.header}>
        <div className={styles.headerTop}>
          <div className={styles.headerLeft}>
            <span className={`${styles.statusDot} ${styles.statusDotStale}`} aria-hidden="true" />
            <span className={styles.cardTitle}>{title ?? '加载失败'}</span>
          </div>
        </div>
      </header>
      <div className={styles.body}>
        <div className={styles.stateCenter}>
          <p className={styles.errorText}>加载失败</p>
          <button type="button" className={styles.retryBtn} onClick={onRetry}>重试</button>
        </div>
      </div>
    </article>
  );
}

// ── Single card (pure display) ────────────────────────────────────────────────

interface SingleCardProps {
  card: ArticleCard;
  /** Show refresh button on this card */
  showRefresh?: boolean;
  refreshing?: boolean;
  onRefresh?: () => void;
  updateInterval?: string;
}

function SingleCard({ card, showRefresh, refreshing, onRefresh, updateInterval }: SingleCardProps) {
  const dotClass = `${styles.statusDot}${card.is_stale ? ` ${styles.statusDotStale}` : ''}`;

  return (
    <article className={styles.card} aria-label={card.card_title}>
      <header className={styles.header}>
        <div className={styles.headerTop}>
          <div className={styles.headerLeft}>
            <span className={dotClass} aria-hidden="true" />
            <span className={styles.cardTitle}>{card.card_title}</span>
            {card.is_stale && (
              <span className={styles.staleTag} title="数据可能过期">过期</span>
            )}
          </div>
          {showRefresh && onRefresh && (
            <button
              type="button"
              className={styles.refreshBtn}
              onClick={onRefresh}
              disabled={refreshing}
              title="刷新数据"
              aria-label="刷新数据"
            >
              <RefreshIcon spinning={!!refreshing} />
            </button>
          )}
        </div>
        <div className={styles.headerMeta}>
          <span className={styles.lastFetch} title={`${card.fetch_age_hours} 小时前更新`}>
            更新于 {formatLocalTime(card.fetch_time)}
          </span>
        </div>
      </header>

      <div className={styles.body}>
        {card.articles.length === 0 ? (
          <div className={styles.stateCenter}>
            <p className={styles.emptyText}>暂无数据</p>
          </div>
        ) : (
          card.articles.map((a) => (
            <ArticleRow key={a.id || a.url} article={a} />
          ))
        )}
      </div>

      {updateInterval && (
        <footer className={styles.footer}>{updateInterval}</footer>
      )}
    </article>
  );
}

// ── PlatformCardGroup — fetches data, renders N independent cards ─────────────
// One group per platform. Each card (section / ranktime) is a separate DOM card.
// The refresh button appears on the FIRST card only; clicking it re-fetches all
// cards for that platform without affecting any other platform.

interface PlatformCardGroupProps {
  platform: string;
  label: string;
  updateInterval?: string;
  onStatusChange?: (platform: string, status: 'loading' | 'ok' | 'error' | 'empty') => void;
}

export function PlatformCardGroup({ platform, label, updateInterval, onStatusChange }: PlatformCardGroupProps) {
  const { data, loading, error, retry } = usePlatformLatest(platform);
  const [refreshing, setRefreshing] = useState(false);

  // Report status to parent for sorting
  useEffect(() => {
    if (!onStatusChange) return;
    if (loading && !data) { onStatusChange(platform, 'loading'); return; }
    if (error)             { onStatusChange(platform, 'error');   return; }
    if (!data || data.cards.length === 0) { onStatusChange(platform, 'empty'); return; }
    onStatusChange(platform, 'ok');
  }, [loading, error, data, platform, onStatusChange]);

  const handleRefresh = useCallback(() => {
    if (refreshing) return;
    setRefreshing(true);
    retry();
    setTimeout(() => setRefreshing(false), 1500);
  }, [refreshing, retry]);

  // ── Loading state: show one skeleton ──
  if (loading && !data) {
    return <PlatformCardSkeleton title={label} />;
  }

  // ── Error state ──
  if (error) {
    return <PlatformCardError title={`${label} · ${error}`} onRetry={retry} />;
  }

  // ── No data ──
  if (!data || data.cards.length === 0) {
    return (
      <article className={styles.card}>
        <header className={styles.header}>
          <div className={styles.headerTop}>
            <div className={styles.headerLeft}>
              <span className={`${styles.statusDot} ${styles.statusDotStale}`} aria-hidden="true" />
              <span className={styles.cardTitle}>{label}</span>
            </div>
          </div>
        </header>
        <div className={styles.body}>
          <div className={styles.stateCenter}>
            <p className={styles.emptyText}>暂无数据</p>
          </div>
        </div>
      </article>
    );
  }

  // ── Render each card independently ──
  // Refresh button only on the first card; spinning while loading or refreshing
  return (
    <>
      {data.cards.map((card) => (
        <SingleCard
          key={card.card_id}
          card={card}
          showRefresh={true}
          refreshing={refreshing || loading}
          onRefresh={handleRefresh}
          updateInterval={updateInterval}
        />
      ))}
    </>
  );
}

// Keep PlatformCard as alias for backward compat
export const PlatformCard = PlatformCardGroup;
export default PlatformCardGroup;
