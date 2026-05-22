# Requirements Document

## Introduction

This document defines the requirements for the News Hotspot Frontend — a React + TypeScript single-page application that provides a visual interface for exploring news hotspot keywords and their associated articles. The frontend consumes data from an existing Django news aggregation backend that scrapes 14 news platforms (domestic Chinese and international), stores articles, and performs keyword analysis (NLP and LLM-based). The core user experience centers on hotspot keywords as the primary navigation element, with trend visualization and associated news articles as supporting views.

## Glossary

- **Frontend_App**: The React + TypeScript single-page application that renders the hotspot keyword interface
- **Keyword_Ranking_Panel**: The left-side panel displaying a ranked list of hotspot keywords with scores and metadata
- **Detail_Panel**: The right-side panel displaying trend charts and associated articles for a selected keyword
- **Trend_Chart**: A line chart showing a keyword's score over the past N days (2 data points per day)
- **Article_List**: A grouped list of news articles associated with a selected keyword, organized by platform
- **News_Feed_Page**: A secondary page showing a chronological timeline of news articles with filtering capabilities
- **Tab_Switcher**: The UI control for switching between "国内热点" (domestic hotspots) and "国际热点" (international hotspots)
- **Backend_API**: The Django REST API providing keyword rankings, trends, articles, and platform metadata
- **Platform_Group**: A classification of news platforms into "domestic" (ftchinese, wsj, kr36, huxiu, zaobao, zhihu, weibo, pengpai) or "international" (economist, apnews, washingtonpost, github, hackernews)
- **Keyword_Score**: A numeric value representing the hotness/importance of a keyword, calculated from weighted frequency and cross-platform coverage
- **Coverage**: The ratio of platforms mentioning a keyword to total platforms in the group

## Requirements

### Requirement 1: Keyword Ranking Display

**User Story:** As a news analyst, I want to see a ranked list of hotspot keywords with their scores and coverage, so that I can quickly identify the most important topics.

#### Acceptance Criteria

1. WHEN the Frontend_App loads, THE Keyword_Ranking_Panel SHALL fetch and display the top keywords from the Backend_API endpoint GET /api/keywords/ranking/
2. THE Keyword_Ranking_Panel SHALL display each keyword with its rank position, keyword text, score, and coverage percentage
3. WHEN the Backend_API returns keyword data, THE Keyword_Ranking_Panel SHALL sort keywords by rank in ascending order (rank 1 at top)
4. THE Keyword_Ranking_Panel SHALL display a trend direction indicator (rising, falling, or stable) for each keyword
5. WHILE the Backend_API request is in progress, THE Keyword_Ranking_Panel SHALL display a loading skeleton placeholder
6. IF the Backend_API request fails, THEN THE Keyword_Ranking_Panel SHALL display an error message with a retry button

### Requirement 2: Domestic and International Tab Switching

**User Story:** As a news analyst, I want to switch between domestic and international hotspot views, so that I can analyze trends in different geographic contexts.

#### Acceptance Criteria

1. THE Tab_Switcher SHALL provide two tabs labeled "国内热点" and "国际热点"
2. WHEN the user selects the "国内热点" tab, THE Keyword_Ranking_Panel SHALL display keywords from the domestic Platform_Group
3. WHEN the user selects the "国际热点" tab, THE Keyword_Ranking_Panel SHALL display keywords from the international Platform_Group
4. THE Tab_Switcher SHALL visually indicate the currently active tab
5. WHEN the user switches tabs, THE Frontend_App SHALL reset the keyword selection state and clear the Detail_Panel content
6. THE Tab_Switcher SHALL default to the "国内热点" tab on initial page load

### Requirement 3: Keyword Selection and Detail View

**User Story:** As a news analyst, I want to click a keyword to see its trend chart and associated articles, so that I can understand the context and trajectory of a topic.

#### Acceptance Criteria

1. WHEN the user clicks a keyword in the Keyword_Ranking_Panel, THE Frontend_App SHALL visually highlight the selected keyword
2. WHEN a keyword is selected, THE Detail_Panel SHALL fetch trend data from GET /api/keywords/trend/ for the selected keyword
3. WHEN a keyword is selected, THE Detail_Panel SHALL fetch associated articles from GET /api/keywords/articles/ for the selected keyword
4. THE Detail_Panel SHALL display the Trend_Chart above the Article_List
5. WHILE the Detail_Panel data is loading, THE Detail_Panel SHALL display loading indicators for both the chart and article sections
6. IF no keyword is selected, THEN THE Detail_Panel SHALL display a placeholder message prompting the user to select a keyword

### Requirement 4: Trend Chart Visualization

**User Story:** As a news analyst, I want to see how a keyword's score has changed over time, so that I can identify emerging or declining topics.

#### Acceptance Criteria

1. WHEN trend data is loaded, THE Trend_Chart SHALL render a line chart with time on the x-axis and Keyword_Score on the y-axis
2. THE Trend_Chart SHALL display data points for the past 7 days by default (approximately 14 data points at 2 per day)
3. THE Trend_Chart SHALL label the x-axis with date values and the y-axis with score values
4. WHEN the user hovers over a data point, THE Trend_Chart SHALL display a tooltip showing the exact score and timestamp
5. IF the Backend_API returns fewer than 2 data points, THEN THE Trend_Chart SHALL display a message indicating insufficient data for trend visualization
6. THE Trend_Chart SHALL use a responsive layout that adapts to the Detail_Panel width

### Requirement 5: Associated Articles Display

**User Story:** As a news analyst, I want to see the news articles associated with a keyword grouped by platform, so that I can understand cross-platform coverage and read source material.

#### Acceptance Criteria

1. WHEN article data is loaded, THE Article_List SHALL display articles grouped by platform name
2. THE Article_List SHALL display each article with its title, platform label, and publication date
3. WHEN the user clicks an article title, THE Frontend_App SHALL open the article URL in a new browser tab
4. THE Article_List SHALL display the platform name as a group header with the article count for that platform
5. THE Article_List SHALL order platform groups by the number of articles in descending order
6. IF no articles are found for the selected keyword, THEN THE Article_List SHALL display a message indicating no associated articles

### Requirement 6: Layout Structure

**User Story:** As a news analyst, I want a clear split-panel layout with keywords on the left and details on the right, so that I can browse and explore simultaneously.

#### Acceptance Criteria

1. THE Frontend_App SHALL use a two-column layout with the Keyword_Ranking_Panel on the left and the Detail_Panel on the right
2. THE Keyword_Ranking_Panel SHALL occupy approximately one-third of the viewport width
3. THE Detail_Panel SHALL occupy approximately two-thirds of the viewport width
4. THE Frontend_App SHALL render the Tab_Switcher above the Keyword_Ranking_Panel
5. WHILE the viewport width is below 768 pixels, THE Frontend_App SHALL stack the panels vertically with the Keyword_Ranking_Panel above the Detail_Panel
6. THE Keyword_Ranking_Panel SHALL support vertical scrolling independently of the Detail_Panel

### Requirement 7: News Feed Page

**User Story:** As a news reader, I want to browse all news articles in chronological order with filtering options, so that I can discover articles beyond keyword-driven exploration.

#### Acceptance Criteria

1. THE News_Feed_Page SHALL fetch articles from GET /api/news/feed/ and display them in reverse chronological order
2. THE News_Feed_Page SHALL provide a platform filter allowing the user to select one or more platforms
3. THE News_Feed_Page SHALL provide a section filter allowing the user to filter by article section
4. WHEN the user applies a filter, THE News_Feed_Page SHALL re-fetch articles matching the selected filter criteria
5. THE News_Feed_Page SHALL display each article with its title, platform label, section, and publication timestamp
6. WHEN the user clicks an article title on the News_Feed_Page, THE Frontend_App SHALL open the article URL in a new browser tab
7. THE News_Feed_Page SHALL implement pagination or infinite scroll to handle large article volumes
8. WHILE the article list is loading, THE News_Feed_Page SHALL display loading indicators

### Requirement 8: Navigation Between Pages

**User Story:** As a user, I want to navigate between the hotspot analysis page and the news feed page, so that I can switch between keyword-driven and chronological browsing modes.

#### Acceptance Criteria

1. THE Frontend_App SHALL provide a navigation bar with links to the hotspot analysis page and the News_Feed_Page
2. THE Frontend_App SHALL highlight the currently active page in the navigation bar
3. WHEN the user navigates between pages, THE Frontend_App SHALL preserve the browser URL using client-side routing
4. THE Frontend_App SHALL default to the hotspot analysis page as the landing page

### Requirement 9: API Integration and Error Handling

**User Story:** As a user, I want the application to handle network errors gracefully, so that I can understand when data is unavailable and retry when possible.

#### Acceptance Criteria

1. WHEN a Backend_API request returns an HTTP error status, THE Frontend_App SHALL display a user-friendly error message describing the failure
2. WHEN a Backend_API request times out after 10 seconds, THE Frontend_App SHALL abort the request and display a timeout message
3. IF a Backend_API request fails, THEN THE Frontend_App SHALL provide a retry mechanism for the failed request
4. THE Frontend_App SHALL configure a base URL for all Backend_API requests, supporting environment-based configuration
5. WHEN the Backend_API returns an empty dataset, THE Frontend_App SHALL display an appropriate empty-state message rather than a blank screen

### Requirement 10: Platform Metadata Display

**User Story:** As a news analyst, I want to see platform metadata such as last fetch time and article count, so that I can assess data freshness and coverage.

#### Acceptance Criteria

1. WHEN the user views platform information, THE Frontend_App SHALL fetch platform metadata from GET /api/platforms/
2. THE Frontend_App SHALL display each platform with its label, group classification, last fetch timestamp, and total article count
3. WHEN the last fetch timestamp is older than 2 hours, THE Frontend_App SHALL visually indicate the platform data may be stale
