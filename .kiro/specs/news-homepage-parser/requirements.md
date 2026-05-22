# Requirements Document

## Introduction

新闻网站首页解析工具（News Homepage Parser）是一个能够接收新闻类网站 URL，自动抓取并解析其首页内容，提取出结构化新闻信息的工具。目标是帮助用户快速获取新闻网站首页的各条新闻标题、链接、所属栏目等关键信息，支持主流新闻网站（如 The Economist、BBC、CNN 等）。

## Glossary

- **Parser**：新闻首页解析器，负责接收 URL、抓取页面内容并提取结构化数据的核心组件
- **NewsItem**：单条新闻条目，包含标题、链接、所属栏目等字段
- **Section**：新闻栏目/分类，如"Politics"、"Technology"、"Business"等
- **Homepage**：网站首页，即用户输入的目标 URL 所对应的页面
- **Fetcher**：负责发起 HTTP 请求、获取页面 HTML 内容的组件
- **Extractor**：负责从 HTML 内容中识别并提取 NewsItem 列表的组件
- **Pretty_Printer**：负责将解析结果格式化输出（如 JSON、表格等）的组件

---

## Requirements

### Requirement 1: 接收并验证输入 URL

**User Story:** As a user, I want to input a news website URL, so that the tool knows which homepage to parse.

#### Acceptance Criteria

1. THE Parser SHALL accept a URL string as input
2. WHEN the input URL uses the `http` or `https` scheme, THE Parser SHALL proceed to fetch the homepage
3. IF the input URL is empty or missing, THEN THE Parser SHALL return an error message indicating the URL is required
4. IF the input URL does not use `http` or `https` scheme, THEN THE Parser SHALL return an error message indicating the URL scheme is invalid
5. IF the input URL is malformed and cannot be parsed as a valid URL, THEN THE Parser SHALL return an error message indicating the URL format is invalid

---

### Requirement 2: 抓取首页 HTML 内容

**User Story:** As a user, I want the tool to fetch the homepage content automatically, so that I don't need to manually download the page.

#### Acceptance Criteria

1. WHEN a valid URL is provided, THE Fetcher SHALL send an HTTP GET request to the URL and retrieve the response body
2. WHEN the HTTP response status code is 200, THE Fetcher SHALL pass the HTML content to the Extractor
3. IF the HTTP response status code is not 200, THEN THE Fetcher SHALL return an error message containing the status code
4. IF the HTTP request times out after 15 seconds, THEN THE Fetcher SHALL return an error message indicating a timeout occurred
5. IF the HTTP request fails due to a network error, THEN THE Fetcher SHALL return an error message describing the network failure
6. WHEN fetching the homepage, THE Fetcher SHALL send a User-Agent header to identify the client

---

### Requirement 3: 提取新闻条目

**User Story:** As a user, I want the tool to extract news items from the homepage, so that I can see all available news in a structured format.

#### Acceptance Criteria

1. WHEN HTML content is provided, THE Extractor SHALL identify and extract all news items present on the homepage
2. FOR EACH extracted NewsItem, THE Extractor SHALL include the news title as a non-empty string
3. FOR EACH extracted NewsItem, THE Extractor SHALL include the news link as an absolute URL
4. WHERE a section/category label is present in the page structure, THE Extractor SHALL include the section name in the corresponding NewsItem
5. WHERE a section/category label is not present, THE Extractor SHALL set the section field to an empty string or null
6. WHEN the extracted news link is a relative URL, THE Extractor SHALL resolve it to an absolute URL using the base URL of the homepage
7. IF no news items can be identified from the HTML content, THEN THE Extractor SHALL return an empty list and a warning message indicating no news items were found

---

### Requirement 4: 格式化输出解析结果

**User Story:** As a user, I want the parsed results to be presented in a readable format, so that I can easily review and use the extracted news information.

#### Acceptance Criteria

1. THE Pretty_Printer SHALL format the list of NewsItems into a structured JSON output by default
2. WHERE the user specifies a table output format, THE Pretty_Printer SHALL render the NewsItems as a formatted table with columns for title, link, and section
3. THE Pretty_Printer SHALL include the total count of extracted NewsItems in the output
4. THE Pretty_Printer SHALL include the source URL and the fetch timestamp in the output

---

### Requirement 5: 解析结果的序列化与反序列化（Round-trip）

**User Story:** As a developer, I want the parsed results to be serializable and deserializable, so that I can store and reload results without data loss.

#### Acceptance Criteria

1. THE Pretty_Printer SHALL serialize a list of NewsItems to a valid JSON string
2. WHEN a valid JSON string produced by the Pretty_Printer is provided, THE Parser SHALL deserialize it back into an equivalent list of NewsItems
3. FOR ALL valid lists of NewsItems, serializing then deserializing SHALL produce a list equivalent to the original (round-trip property)
4. IF the JSON string is malformed, THEN THE Parser SHALL return an error message indicating deserialization failed

---

### Requirement 6: 支持多个主流新闻网站

**User Story:** As a user, I want the tool to work with major news websites, so that I can parse homepages from different sources.

#### Acceptance Criteria

1. WHEN the homepage URL belongs to a supported news website, THE Extractor SHALL extract NewsItems with a non-empty title and link for each item
2. THE Parser SHALL support parsing homepages from at least the following websites: The Economist (economist.com), BBC News (bbc.com), CNN (cnn.com)
3. IF the homepage structure is not recognized by any known extraction strategy, THEN THE Extractor SHALL attempt a generic extraction strategy based on common HTML patterns (e.g., `<article>`, `<h2>`, `<a>` tags)
4. WHEN the generic extraction strategy is used, THE Extractor SHALL include a notice in the output indicating that generic extraction was applied

---

### Requirement 7: 错误处理与健壮性

**User Story:** As a user, I want the tool to handle errors gracefully, so that I receive clear feedback when something goes wrong.

#### Acceptance Criteria

1. IF any component encounters an unhandled exception, THEN THE Parser SHALL catch the exception and return a structured error response containing the error type and message
2. WHEN an error occurs, THE Parser SHALL log the error details for diagnostic purposes
3. THE Parser SHALL complete execution and return a response within 30 seconds for any input URL
