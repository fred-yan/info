import type { ArticleListProps } from '../../types';
import { groupArticlesByPlatform } from '../../utils/transformations';
import { EmptyState } from '../EmptyState';
import styles from './ArticleList.module.css';

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function ArticleList({ articles }: ArticleListProps) {
  if (articles.length === 0) {
    return <EmptyState message="暂无相关文章" />;
  }

  const groups = groupArticlesByPlatform(articles);

  return (
    <div className={styles.container}>
      {groups.map((group) => (
        <div key={group.platform} className={styles.platformGroup}>
          <div className={styles.groupHeader}>
            <span>{group.platform}</span>
            <span className={styles.articleCount}>({group.count})</span>
          </div>
          {group.articles.map((article) => (
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
                <span>{formatDate(article.date)}</span>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
