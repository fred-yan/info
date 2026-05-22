import type { ArticleDetail } from '../../types';
import { EmptyState } from '../EmptyState';
import { LoadingSkeleton } from '../LoadingSkeleton';
import styles from './ArticleFeedList.module.css';

interface ArticleFeedListProps {
  articles: ArticleDetail[];
  loading: boolean;
}

function formatDateTime(dateStr: string): string {
  const date = new Date(dateStr);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

export function ArticleFeedList({ articles, loading }: ArticleFeedListProps) {
  if (loading) {
    return <LoadingSkeleton rows={8} />;
  }

  if (articles.length === 0) {
    return <EmptyState message="暂无文章" />;
  }

  return (
    <div className={styles.container}>
      {articles.map((article) => (
        <div key={article.id} className={styles.articleItem}>
          <a
            className={styles.articleTitle}
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            {article.title}
          </a>
          <div className={styles.articleMeta}>
            <span className={styles.platformLabel}>{article.platform}</span>
            <span className={styles.sectionLabel}>{article.section}</span>
            <span className={styles.timestamp}>{formatDateTime(article.date)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
