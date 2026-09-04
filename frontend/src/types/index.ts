// === API Response Types ===

export interface KeywordRankingResponse {
  analysis_time: string;
  group: string;
  keywords: KeywordData[];
}

export interface KeywordData {
  keyword: string;
  score: number;
  rank: number;
  count: number;
  platform_count: number;
  coverage: number;
  sources: string[];
  sample_articles: ArticleSummary[];
  trend_direction?: 'rising' | 'falling' | 'stable';
}

export interface ArticleSummary {
  title: string;
  url: string;
  platform: string;
}

export interface TrendDataPoint {
  timestamp: string; // ISO 8601
  score: number;
}

export interface TrendResponse {
  keyword: string;
  data_points: TrendDataPoint[];
}

export interface ArticleDetail {
  id: number;
  title: string;
  url: string;
  platform: string;
  section: string;
  date: string; // ISO 8601
  rank?: number | null;
  ranktime?: string;
}

export interface ArticlesResponse {
  keyword: string;
  articles: ArticleDetail[];
}

export interface PlatformMetadata {
  name: string;
  label: string;
  group: 'domestic' | 'international';
  last_fetch: string; // ISO 8601
  article_count: number;
  update_interval: string; // e.g. "每6小时更新"
}

export interface NewsFeedResponse {
  articles: ArticleDetail[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
}

// === Component Prop Interfaces ===

export interface KeywordItemProps {
  data: KeywordData;
  isSelected: boolean;
  onClick: (keyword: string) => void;
}

export interface TrendChartProps {
  data: TrendDataPoint[];
  keyword: string;
}

export interface ArticleListProps {
  articles: ArticleDetail[];
}

export interface FilterBarProps {
  platforms: string[];
  sections: string[];
  selectedPlatforms: string[];
  selectedSection: string | null;
  onPlatformChange: (platforms: string[]) => void;
  onSectionChange: (section: string | null) => void;
}

// === App State Types ===

export interface AppState {
  activeGroup: 'domestic' | 'international';
  selectedKeyword: string | null;
  currentPage: 'hotspot' | 'feed';
}

// === Utility Types ===

export interface PlatformArticleGroup {
  platform: string;
  articles: ArticleDetail[];
  count: number;
}

// === Multi-Platform Page Types ===

export type PlatformGroup = 'domestic' | 'international';

export interface PlatformFeedResult {
  articles: ArticleDetail[];
  loading: boolean;
  error: string | null;
}

// === Platform Latest Types ===

/** 单条新闻条目（来自 news/latest/ 接口） */
export interface LatestArticle {
  index: number;        // 去重后重新编号，从 1 开始
  id: number;
  title: string;
  url: string;
  section: string;
  rank: number | null;
  ranktime: string;
}

/** 一张独立卡片（对应某平台的某个 section/ranktime 分组） */
export interface ArticleCard {
  card_id: string;          // e.g. "section" | "hotlist_24hour"
  card_title: string;       // e.g. "FT中文网 · 首页资讯"
  platform: string;
  platform_label: string;
  fetch_time: string;       // ISO 8601，截断到分钟
  fetch_age_hours: number;
  is_stale: boolean;
  articles: LatestArticle[];
  update_interval?: string; // e.g. "每6小时更新"，从 platforms 元数据注入
}

/** /api/news/latest/ 返回结构 */
export interface PlatformLatestResponse {
  cards: ArticleCard[];
}

export interface UsePlatformLatestResult {
  data: PlatformLatestResponse | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
}
