import { useRef, useEffect } from 'react';
import { useKeywordRanking } from '../../hooks/useKeywordRanking';
import { sortKeywordsByRank } from '../../utils/transformations';
import { KeywordItem } from './KeywordItem';
import { LoadingSkeleton } from '../LoadingSkeleton';
import { ErrorState } from '../ErrorState';
import './KeywordRankingPanel.css';

interface KeywordRankingPanelProps {
  group: 'domestic' | 'international';
  selectedKeyword: string | null;
  onKeywordSelect: (keyword: string) => void;
  onFirstKeywordLoaded?: (keyword: string) => void;
}

export function KeywordRankingPanel({
  group,
  selectedKeyword,
  onKeywordSelect,
  onFirstKeywordLoaded,
}: KeywordRankingPanelProps) {
  const { data, loading, error, retry } = useKeywordRanking(group);

  // 数据首次加载完成时，通知父组件第一个热词
  const notifiedRef = useRef<string | null>(null);
  useEffect(() => {
    if (!loading && !error && data) {
      const sorted = sortKeywordsByRank(data);
      if (sorted.length > 0 && onFirstKeywordLoaded) {
        const first = sorted[0].keyword;
        if (notifiedRef.current !== first) {
          notifiedRef.current = first;
          onFirstKeywordLoaded(first);
        }
      }
    }
  }, [loading, error, data, onFirstKeywordLoaded]);

  if (loading) {
    return (
      <div className="keyword-ranking-panel">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="keyword-ranking-panel">
        <ErrorState message={error} onRetry={retry} />
      </div>
    );
  }

  const sortedKeywords = data ? sortKeywordsByRank(data) : [];

  return (
    <div className="keyword-ranking-panel">
      <div className="keyword-ranking-panel__list" role="list">
        {sortedKeywords.map((keyword) => (
          <div key={keyword.keyword} role="listitem">
            <KeywordItem
              data={keyword}
              isSelected={keyword.keyword === selectedKeyword}
              onClick={onKeywordSelect}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export default KeywordRankingPanel;
