import type { ArticleDetail } from '../../types';
import styles from './NewsItem.module.css';

// Maps internal section keys to friendly labels
const SECTION_LABELS: Record<string, string> = {
  section_1: '头条',
  section_2: '要闻',
  section_3: '热点',
  hotlist: '热榜',
  most_read: '热读',
  top: '置顶',
  trending: '趋势',
  daily: '日榜',
  weekly: '周榜',
  monthly: '月榜',
};

function getSectionLabel(section: string): string | null {
  if (!section) return null;
  return SECTION_LABELS[section] ?? null;
}

interface NewsItemProps {
  article: ArticleDetail;
  rank: number;
}

export function NewsItem({ article, rank }: NewsItemProps) {
  const sectionLabel = getSectionLabel(article.section);
  const isTop = rank <= 3;

  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className={styles.item}
      title={article.title}
    >
      <span className={`${styles.rank}${isTop ? ` ${styles.rankTop}` : ''}`}>
        {rank}
      </span>
      <span className={styles.title}>{article.title}</span>
      {sectionLabel && (
        <span className={styles.section} aria-label={`栏目: ${sectionLabel}`}>
          {sectionLabel}
        </span>
      )}
    </a>
  );
}

export default NewsItem;
