import { useState } from 'react';
import { TabSwitcher } from '../components/TabSwitcher';
import { KeywordRankingPanel } from '../components/KeywordRankingPanel';
import { DetailPanel } from '../components/DetailPanel';
import styles from './HotspotPage.module.css';

export function HotspotPage() {
  const [activeGroup, setActiveGroup] = useState<'domestic' | 'international'>('domestic');
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);

  const handleGroupChange = (group: 'domestic' | 'international') => {
    setActiveGroup(group);
    setSelectedKeyword(null);
  };

  return (
    <div className={styles.container}>
      <div className={styles.leftPanel}>
        <TabSwitcher activeGroup={activeGroup} onGroupChange={handleGroupChange} />
        <KeywordRankingPanel
          group={activeGroup}
          selectedKeyword={selectedKeyword}
          onKeywordSelect={setSelectedKeyword}
        />
      </div>
      <div className={styles.rightPanel}>
        <DetailPanel keyword={selectedKeyword} group={activeGroup} />
      </div>
    </div>
  );
}

export default HotspotPage;
