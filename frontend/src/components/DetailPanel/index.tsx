import { useKeywordTrend } from '../../hooks/useKeywordTrend';
import { useKeywordArticles } from '../../hooks/useKeywordArticles';
import { TrendChart } from '../TrendChart';
import { ArticleList } from '../ArticleList';
import { LoadingSkeleton } from '../LoadingSkeleton';
import { EmptyState } from '../EmptyState';
import styles from './DetailPanel.module.css';

interface DetailPanelProps {
  keyword: string | null;
  group: 'domestic' | 'international';
}

export function DetailPanel({ keyword, group }: DetailPanelProps) {
  const { data: trendData, loading: trendLoading } = useKeywordTrend(keyword, group);
  const { data: articlesData, loading: articlesLoading } = useKeywordArticles(keyword, group);

  if (!keyword) {
    return (
      <div className={styles.container}>
        <EmptyState message="请选择一个关键词查看详情" />
      </div>
    );
  }

  const isLoading = trendLoading || articlesLoading;

  if (isLoading) {
    return (
      <div className={styles.container}>
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.trendSection}>
        {trendData && <TrendChart data={trendData} keyword={keyword} />}
      </div>
      <div className={styles.articlesSection}>
        {articlesData && <ArticleList articles={articlesData} />}
      </div>
    </div>
  );
}
