import type { KeywordData, ArticleDetail, PlatformArticleGroup } from '../types';

/**
 * Sorts keywords by rank in ascending order.
 */
export function sortKeywordsByRank(keywords: KeywordData[]): KeywordData[] {
  return [...keywords].sort((a, b) => a.rank - b.rank);
}

/**
 * Determines trend direction from two score values.
 */
export function computeTrendDirection(
  current: number,
  previous: number
): 'rising' | 'falling' | 'stable' {
  if (current > previous) return 'rising';
  if (current < previous) return 'falling';
  return 'stable';
}

/**
 * Groups articles by platform, sorted by group size descending.
 */
export function groupArticlesByPlatform(
  articles: ArticleDetail[]
): PlatformArticleGroup[] {
  const groups = new Map<string, ArticleDetail[]>();
  for (const article of articles) {
    const list = groups.get(article.platform) || [];
    list.push(article);
    groups.set(article.platform, list);
  }
  return Array.from(groups.entries())
    .map(([platform, articles]) => ({ platform, articles, count: articles.length }))
    .sort((a, b) => b.count - a.count);
}

/**
 * Checks if a timestamp is older than the given threshold in hours.
 * Defaults to 2 hours if no threshold is provided.
 */
export function isStale(timestamp: string, thresholdHours: number = 2): boolean {
  const fetchTime = new Date(timestamp).getTime();
  const now = Date.now();
  return (now - fetchTime) > thresholdHours * 60 * 60 * 1000;
}

/**
 * Maps HTTP status codes to user-friendly Chinese error messages.
 */
export function mapHttpErrorToMessage(status: number): string {
  if (status === 404) return '数据未找到，请稍后重试';
  if (status === 408 || status === 504) return '请求超时，请检查网络连接';
  if (status >= 500) return '服务器错误，请稍后重试';
  if (status >= 400) return '请求错误，请刷新页面';
  return '未知错误';
}

/**
 * Formats a score number to 1 decimal place.
 */
export function formatScore(score: number): string {
  return score.toFixed(1);
}

/**
 * Formats a coverage value (0-1) as a percentage string.
 * e.g., 0.75 -> "75%"
 */
export function formatCoverage(coverage: number): string {
  return `${Math.round(coverage * 100)}%`;
}
