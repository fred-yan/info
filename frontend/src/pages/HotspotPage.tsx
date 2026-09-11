import { useState, useCallback, useEffect, useRef } from 'react';
import { TabSwitcher } from '../components/TabSwitcher';
import { KeywordRankingPanel } from '../components/KeywordRankingPanel';
import { DetailPanel } from '../components/DetailPanel';
import { BottomSheet } from '../components/BottomSheet';
import styles from './HotspotPage.module.css';

function useIsMobile(breakpoint = 768): boolean {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= breakpoint);

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${breakpoint}px)`);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [breakpoint]);

  return isMobile;
}

export function HotspotPage() {
  const [activeGroup, setActiveGroup] = useState<'domestic' | 'international'>('domestic');
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const isMobile = useIsMobile();
  const rightPanelRef = useRef<HTMLDivElement>(null);

  const handleGroupChange = useCallback((group: 'domestic' | 'international') => {
    setActiveGroup(group);
    setSelectedKeyword(null);
    setSheetOpen(false);
  }, []);

  const handleKeywordSelect = useCallback((keyword: string) => {
    setSelectedKeyword(keyword);
    if (isMobile) {
      setSheetOpen(true);
    } else {
      // 桌面端：把右侧详情面板滚到顶部，确保用户能看到更新的内容
      rightPanelRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [isMobile]);

  const handleSheetClose = useCallback(() => {
    setSheetOpen(false);
  }, []);

  return (
    <div className={styles.container}>
      {/* 左侧：词条榜单（桌面端约1/3，移动端全宽） */}
      <div className={styles.leftPanel}>
        <TabSwitcher activeGroup={activeGroup} onGroupChange={handleGroupChange} />
        <KeywordRankingPanel
          group={activeGroup}
          selectedKeyword={selectedKeyword}
          onKeywordSelect={handleKeywordSelect}
        />
      </div>

      {/* 右侧：详情面板（仅桌面端展示） */}
      {!isMobile && (
        <div className={styles.rightPanel} ref={rightPanelRef}>
          <DetailPanel keyword={selectedKeyword} group={activeGroup} />
        </div>
      )}

      {/* 移动端：Bottom Sheet */}
      {isMobile && (
        <BottomSheet
          open={sheetOpen}
          title={selectedKeyword ?? ''}
          onClose={handleSheetClose}
        >
          <DetailPanel keyword={selectedKeyword} group={activeGroup} />
        </BottomSheet>
      )}
    </div>
  );
}
