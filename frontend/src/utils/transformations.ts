import type { KeywordData, ArticleDetail, PlatformArticleGroup } from '../types';

/**
 * 平台名称到中文标签的映射，与后端 PLATFORM_LABELS 保持一致。
 */
export const PLATFORM_LABELS: Record<string, string> = {
  ftchinese:    'FT中文网',
  wsj:          '华尔街日报中文版',
  kr36:         '36氪',
  huxiu:        '虎嗅',
  tmtpost:      '钛媒体',
  jiqizhixin:   '机器之心',
  cls:          '财联社',
  wscn:         '华尔街见闻',
  zaobao:       '联合早报',
  zhihu:        '知乎',
  weibo:        '微博',
  pengpai:      '澎湃新闻',
  economist:    'The Economist',
  apnews:       'AP News',
  washingtonpost: 'Washington Post',
  theverge:     'The Verge',
  techcrunch:   'TechCrunch',
  mittr:        'MIT Technology Review',
  github:       'GitHub Trending',
  hackernews:   'Hacker News',
};

/**
 * 将平台 key 转为中文显示名，未知平台原样返回。
 */
export function getPlatformLabel(platform: string): string {
  return PLATFORM_LABELS[platform] ?? platform;
}
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
 * Defaults to 8 hours — data is fetched every 6 hours, so anything
 * within that window is still considered fresh.
 */
export function isStale(timestamp: string, thresholdHours: number = 8): boolean {
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
  if (status === 503) return '资讯获取错误';
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
