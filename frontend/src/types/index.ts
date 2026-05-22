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

export interface FeedFilters {
  platforms: string[];
  section: string | null;
}
