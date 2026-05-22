# Implementation Plan: News Hotspot Frontend

## Overview

This plan implements a React + TypeScript single-page application using Vite, React Router v6, Recharts, and Vitest. The implementation proceeds from project scaffolding and core utilities, through data layer and components, to page assembly and integration wiring.

## Tasks

- [x] 1. Set up project structure and core infrastructure
  - [x] 1.1 Initialize Vite + React + TypeScript project
    - Run `npm create vite@latest` with React + TypeScript template in a `frontend/` directory
    - Install dependencies: react-router-dom, recharts, fast-check (dev)
    - Configure Vitest and React Testing Library in vite.config.ts
    - Set up directory structure: `src/api/`, `src/hooks/`, `src/components/`, `src/pages/`, `src/utils/`, `src/types/`
    - Configure environment variable `VITE_API_BASE_URL` in `.env` and `.env.example`
    - _Requirements: 9.4_

  - [x] 1.2 Define TypeScript interfaces and types
    - Create `src/types/index.ts` with all API response types: `KeywordRankingResponse`, `KeywordData`, `TrendDataPoint`, `TrendResponse`, `ArticleDetail`, `ArticlesResponse`, `PlatformMetadata`, `NewsFeedResponse`
    - Define component prop interfaces: `KeywordItemProps`, `TrendChartProps`, `ArticleListProps`, `FilterBarProps`
    - Define app state type: `AppState` with `activeGroup`, `selectedKeyword`, `currentPage`
    - _Requirements: 1.2, 3.2, 5.2, 7.5_

- [x] 2. Implement API client and utility functions
  - [x] 2.1 Implement API client with timeout and error handling
    - Create `src/api/client.ts` with `ApiClient` class
    - Implement `get<T>()` method with AbortController-based 10-second timeout
    - Implement typed `ApiError` class with status code and message
    - Configure base URL from `import.meta.env.VITE_API_BASE_URL` with `/api` fallback
    - Export singleton `apiClient` instance
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 2.2 Implement pure transformation functions
    - Create `src/utils/transformations.ts`
    - Implement `sortKeywordsByRank(keywords: KeywordData[]): KeywordData[]`
    - Implement `computeTrendDirection(current: number, previous: number): 'rising' | 'falling' | 'stable'`
    - Implement `groupArticlesByPlatform(articles: ArticleDetail[]): PlatformArticleGroup[]`
    - Implement `isStale(timestamp: string, thresholdHours: number): boolean`
    - Implement `mapHttpErrorToMessage(status: number): string`
    - Implement `formatScore(score: number): string` and `formatCoverage(coverage: number): string`
    - _Requirements: 1.3, 1.4, 5.1, 5.4, 5.5, 9.1, 10.3_

  - [x]* 2.3 Write property tests for sortKeywordsByRank
    - **Property 2: Keyword list sorting invariant**
    - **Validates: Requirements 1.3**

  - [x]* 2.4 Write property tests for computeTrendDirection
    - **Property 3: Trend direction computation correctness**
    - **Validates: Requirements 1.4**

  - [x]* 2.5 Write property tests for groupArticlesByPlatform
    - **Property 6: Article grouping correctness**
    - **Property 7: Platform group ordering invariant**
    - **Validates: Requirements 5.1, 5.4, 5.5**

  - [x]* 2.6 Write property tests for isStale
    - **Property 12: Platform staleness detection**
    - **Validates: Requirements 10.3**

  - [x]* 2.7 Write property tests for mapHttpErrorToMessage
    - **Property 10: HTTP error message mapping completeness**
    - **Validates: Requirements 9.1**

- [x] 3. Checkpoint - Core utilities verified
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement custom data-fetching hooks
  - [x] 4.1 Implement useKeywordRanking hook
    - Create `src/hooks/useKeywordRanking.ts`
    - Accept `group: 'domestic' | 'international'` parameter
    - Fetch from `/api/keywords/ranking/` with group query param
    - Return `{ data, loading, error, retry }` state
    - Re-fetch when group changes; cancel in-flight requests on unmount
    - _Requirements: 1.1, 1.5, 1.6, 2.2, 2.3_

  - [x] 4.2 Implement useKeywordTrend hook
    - Create `src/hooks/useKeywordTrend.ts`
    - Accept `keyword: string | null` and `group: string` parameters
    - Fetch from `/api/keywords/trend/` with keyword, group, and days=7 params
    - Only fetch when keyword is non-null; return null data otherwise
    - _Requirements: 3.2, 4.1, 4.2_

  - [x] 4.3 Implement useKeywordArticles hook
    - Create `src/hooks/useKeywordArticles.ts`
    - Accept `keyword: string | null` and `group: string` parameters
    - Fetch from `/api/keywords/articles/` with keyword and group params
    - Only fetch when keyword is non-null
    - _Requirements: 3.3, 5.1_

  - [x] 4.4 Implement useNewsFeed hook
    - Create `src/hooks/useNewsFeed.ts`
    - Accept `filters: { platforms: string[], section: string | null }` and `page: number`
    - Fetch from `/api/news/feed/` with platform, section, and page params
    - Re-fetch when filters or page change
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.7_

  - [x] 4.5 Implement usePlatforms hook
    - Create `src/hooks/usePlatforms.ts`
    - Fetch from `/api/platforms/`
    - Return platform metadata array with loading/error states
    - _Requirements: 10.1, 10.2_

  - [x]* 4.6 Write unit tests for custom hooks
    - Test useKeywordRanking loading, success, error, and retry states
    - Test useKeywordTrend skips fetch when keyword is null
    - Test useNewsFeed re-fetches on filter change
    - Mock fetch API for all hook tests
    - _Requirements: 1.5, 1.6, 3.2, 3.3, 9.2, 9.3_

- [x] 5. Implement shared UI components
  - [x] 5.1 Implement LoadingSkeleton and ErrorState components
    - Create `src/components/LoadingSkeleton/index.tsx` with animated placeholder
    - Create `src/components/ErrorState/index.tsx` with error message and retry button
    - Create `src/components/EmptyState/index.tsx` with configurable message
    - _Requirements: 1.5, 1.6, 9.1, 9.5_

  - [x] 5.2 Implement NavBar component
    - Create `src/components/NavBar/index.tsx`
    - Render navigation links to hotspot page and news feed page
    - Highlight active page using React Router's NavLink
    - _Requirements: 8.1, 8.2_

  - [x] 5.3 Implement TabSwitcher component
    - Create `src/components/TabSwitcher/index.tsx`
    - Render two tabs: "国内热点" and "国际热点"
    - Accept `activeGroup` and `onGroupChange` props
    - Visually indicate active tab with styling
    - _Requirements: 2.1, 2.4, 2.6_

- [x] 6. Implement Hotspot Analysis page components
  - [x] 6.1 Implement KeywordItem component
    - Create `src/components/KeywordRankingPanel/KeywordItem.tsx`
    - Display rank position, keyword text, score (formatted), and coverage percentage
    - Display trend direction indicator (arrow up/down/dash icons)
    - Accept `isSelected` prop for highlight styling
    - Handle click to trigger `onClick` callback
    - _Requirements: 1.2, 1.4, 3.1_

  - [x]* 6.2 Write property test for keyword data rendering completeness
    - **Property 1: Keyword data rendering completeness**
    - **Validates: Requirements 1.2**

  - [x] 6.3 Implement KeywordRankingPanel component
    - Create `src/components/KeywordRankingPanel/index.tsx`
    - Use `useKeywordRanking` hook with current group
    - Render sorted list of KeywordItem components
    - Show LoadingSkeleton while loading, ErrorState on error
    - Support independent vertical scrolling
    - _Requirements: 1.1, 1.3, 1.5, 1.6, 6.6_

  - [x] 6.4 Implement TrendChart component
    - Create `src/components/TrendChart/index.tsx`
    - Use Recharts LineChart with ResponsiveContainer
    - Plot time on x-axis (date labels) and score on y-axis
    - Add Tooltip for hover showing exact score and timestamp
    - Show "insufficient data" message when fewer than 2 data points
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 6.5 Implement ArticleList component with platform grouping
    - Create `src/components/ArticleList/index.tsx`
    - Use `groupArticlesByPlatform` to organize articles
    - Render platform name as group header with article count
    - Render each article with title (as link opening in new tab), platform label, and date
    - Show EmptyState when no articles
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 6.6 Implement DetailPanel component
    - Create `src/components/DetailPanel/index.tsx`
    - Use `useKeywordTrend` and `useKeywordArticles` hooks
    - Render TrendChart above ArticleList
    - Show loading indicators while data loads
    - Show placeholder message when no keyword is selected
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x]* 6.7 Write property test for tab switch resets selection
    - **Property 4: Tab switch resets selection state**
    - **Validates: Requirements 2.5**

- [x] 7. Checkpoint - Hotspot components verified
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement News Feed page components
  - [x] 8.1 Implement FilterBar component
    - Create `src/components/FilterBar/index.tsx`
    - Render platform multi-select filter using platform metadata
    - Render section single-select filter
    - Call `onPlatformChange` and `onSectionChange` callbacks on selection
    - _Requirements: 7.2, 7.3_

  - [x] 8.2 Implement ArticleFeedList component
    - Create `src/components/ArticleFeedList/index.tsx`
    - Render articles in reverse chronological order
    - Display title (link to new tab), platform label, section, and publication timestamp
    - Show loading indicators while fetching
    - _Requirements: 7.1, 7.5, 7.6, 7.8_

  - [x] 8.3 Implement Pagination component
    - Create `src/components/Pagination/index.tsx`
    - Accept `page`, `hasNext`, `onPageChange` props
    - Render previous/next navigation buttons
    - Disable previous on page 1, disable next when `hasNext` is false
    - _Requirements: 7.7_

  - [x]* 8.4 Write property test for news feed chronological ordering
    - **Property 8: News feed chronological ordering**
    - **Validates: Requirements 7.1**

  - [x]* 8.5 Write property test for filter-to-API parameter mapping
    - **Property 9: Filter-to-API parameter mapping**
    - **Validates: Requirements 7.4**

- [x] 9. Assemble pages and routing
  - [x] 9.1 Implement HotspotPage
    - Create `src/pages/HotspotPage.tsx`
    - Compose TabSwitcher, KeywordRankingPanel, and DetailPanel
    - Manage `activeGroup` and `selectedKeyword` state
    - Reset `selectedKeyword` to null when group changes
    - Apply two-column layout: 1/3 left panel, 2/3 right panel
    - Stack vertically below 768px viewport width
    - _Requirements: 2.5, 2.6, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 9.2 Implement NewsFeedPage
    - Create `src/pages/NewsFeedPage.tsx`
    - Compose FilterBar, ArticleFeedList, and Pagination
    - Manage filter state and page number
    - Use `useNewsFeed` hook with current filters and page
    - Use `usePlatforms` hook to populate filter options
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.7, 7.8_

  - [x] 9.3 Configure React Router and App shell
    - Create `src/App.tsx` with React Router BrowserRouter
    - Define routes: `/` → HotspotPage, `/feed` → NewsFeedPage
    - Include NavBar in the layout
    - Add top-level Error Boundary
    - Default route to HotspotPage
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x]* 9.4 Write property test for keyword selection triggers correct fetches
    - **Property 5: Keyword selection triggers correct data fetches**
    - **Validates: Requirements 3.2, 3.3**

  - [x]* 9.5 Write property test for empty dataset produces empty-state
    - **Property 11: Empty dataset produces empty-state message**
    - **Validates: Requirements 9.5**

- [x] 10. Implement platform metadata display
  - [x] 10.1 Implement PlatformStatus component
    - Create `src/components/PlatformStatus/index.tsx`
    - Display each platform with label, group, last fetch timestamp, and article count
    - Use `isStale()` to visually indicate stale platforms (last fetch > 2 hours)
    - Integrate into NavBar or as a dedicated section accessible from navigation
    - _Requirements: 10.1, 10.2, 10.3_

- [x] 11. Final checkpoint - Full integration verified
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The frontend assumes backend API endpoints exist; if new endpoints are not yet implemented, mock responses can be used during development
- All text labels use Chinese where specified in requirements (e.g., tab labels, error messages)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "2.2"] },
    { "id": 3, "tasks": ["2.3", "2.4", "2.5", "2.6", "2.7"] },
    { "id": 4, "tasks": ["4.1", "4.2", "4.3", "4.4", "4.5", "5.1", "5.2", "5.3"] },
    { "id": 5, "tasks": ["4.6", "6.1", "6.4", "6.5", "8.1", "8.3"] },
    { "id": 6, "tasks": ["6.2", "6.3", "6.6", "8.2"] },
    { "id": 7, "tasks": ["6.7", "8.4", "8.5"] },
    { "id": 8, "tasks": ["9.1", "9.2"] },
    { "id": 9, "tasks": ["9.3", "9.4", "9.5", "10.1"] }
  ]
}
```
