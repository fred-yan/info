import { useState, useMemo, useCallback } from 'react';
import { usePlatforms } from '../hooks/usePlatforms';
import { MultiPlatformGrid } from '../components/MultiPlatformGrid';
import type { PlatformGroup } from '../types';
import styles from './MultiPlatformPage.module.css';

const TABS: { key: PlatformGroup; label: string }[] = [
  { key: 'domestic', label: '国内热点' },
  { key: 'international', label: '国际热点' },
];

export function MultiPlatformPage() {
  const [activeGroup, setActiveGroup] = useState<PlatformGroup>('domestic');
  const { data: platforms, loading, error, retry } = usePlatforms();

  const handleGroupChange = useCallback((group: PlatformGroup) => {
    setActiveGroup(group);
  }, []);

  const filteredPlatforms = useMemo(() => {
    if (!platforms) return [];
    return platforms.filter((p) => p.group === activeGroup);
  }, [platforms, activeGroup]);

  return (
    <div className={styles.page}>
      {/* Group Tab Bar */}
      <div className={styles.tabBar} role="tablist" aria-label="平台分组">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            role="tab"
            aria-selected={activeGroup === tab.key}
            className={`${styles.tab}${activeGroup === tab.key ? ` ${styles.tabActive}` : ''}`}
            onClick={() => handleGroupChange(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className={styles.banner} aria-busy="true">
          <span>加载平台信息…</span>
        </div>
      ) : error ? (
        <div className={`${styles.banner} ${styles.bannerError}`} role="alert">
          <span>{error}</span>
          <button type="button" className={styles.retryBtn} onClick={retry}>重试</button>
        </div>
      ) : filteredPlatforms.length === 0 ? (
        <div className={styles.empty}><span>当前分组暂无平台数据</span></div>
      ) : (
        <div className={styles.gridWrapper}>
          <MultiPlatformGrid platforms={filteredPlatforms} />
        </div>
      )}
    </div>
  );
}

export default MultiPlatformPage;
