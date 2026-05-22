# Implementation Plan: News Homepage Parser

## Overview

基于 Python 实现命令行新闻首页解析工具，依次实现 URL 验证、HTTP 抓取、HTML 提取、格式化输出四个核心组件，最后通过 CLI 入口将各组件串联。

## Tasks

- [x] 1. 初始化项目结构与数据模型
  - 创建项目目录结构：`news_homepage_parser/`（主包）和 `tests/`
  - 创建 `news_homepage_parser/models.py`，定义 `NewsItem` 和 `ParseResult` dataclass
  - 创建 `pyproject.toml` 或 `requirements.txt`，声明依赖：`requests`、`beautifulsoup4`、`rich`、`hypothesis`
  - _Requirements: 3.2, 3.3, 3.4, 4.3, 4.4_

- [x] 2. 实现 URL 验证器
  - [x] 2.1 在 `news_homepage_parser/validator.py` 中实现 `validate_url(url: str) -> tuple[bool, str]`
    - 检查 URL 非空（Requirements 1.3）
    - 检查 scheme 为 http 或 https（Requirements 1.4）
    - 检查 URL 格式合法（Requirements 1.5）
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x]* 2.2 在 `tests/test_validator.py` 中为 `validate_url` 编写单元测试
    - 测试空 URL 返回错误（Requirements 1.3）
    - 测试非 http/https scheme 返回错误（Requirements 1.4）
    - 测试格式非法 URL 返回错误（Requirements 1.5）
    - 测试合法 http/https URL 通过验证（Requirements 1.1, 1.2）
    - _Requirements: 1.3, 1.4, 1.5_

  - [x]* 2.3 在 `tests/test_validator.py` 中编写属性测试 P1
    - **Property 1: Invalid URL validation**
    - **Validates: Requirements 1.3, 1.4, 1.5**
    - 使用 Hypothesis 生成非 http/https URL 字符串，验证 `validate_url` 始终返回错误

- [x] 3. 实现 Fetcher
  - [x] 3.1 在 `news_homepage_parser/fetcher.py` 中实现 `fetch(url: str, timeout: int = 15) -> tuple[bool, str]`
    - 发送 GET 请求，携带 User-Agent header（Requirements 2.6）
    - 检查 HTTP 状态码，非 200 返回含状态码的错误（Requirements 2.3）
    - 处理超时异常，返回超时错误（Requirements 2.4）
    - 处理网络异常，返回网络错误（Requirements 2.5）
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x]* 3.2 在 `tests/test_fetcher.py` 中为 `fetch` 编写单元测试（使用 `unittest.mock`）
    - 测试 HTTP 200 时正常返回 HTML（Requirements 2.2）
    - 测试 HTTP 非 200 时返回含状态码的错误（Requirements 2.3）
    - 测试超时时返回超时错误（Requirements 2.4）
    - 测试网络错误时返回网络错误（Requirements 2.5）
    - 测试请求携带 User-Agent header（Requirements 2.6）
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x]* 3.3 在 `tests/test_fetcher.py` 中编写属性测试 P2
    - **Property 2: Non-200 HTTP status returns error containing status code**
    - **Validates: Requirements 2.3**
    - 使用 Hypothesis 生成非 200 状态码，mock HTTP 响应，验证错误消息包含该状态码

- [x] 4. Checkpoint — 确保所有测试通过
  - 运行 `pytest tests/test_validator.py tests/test_fetcher.py`，确保全部通过，如有问题请告知。

- [x] 5. 实现 Extractor
  - [x] 5.1 在 `news_homepage_parser/extractor.py` 中实现站点策略分发逻辑
    - 根据域名匹配 Economist、BBC、CNN 专用策略（Requirements 6.2）
    - 无匹配时降级为通用策略（Requirements 6.3）
    - 通用策略基于 `<article>`、`<h2>`、`<a>` 标签提取（Requirements 6.3）
    - 使用通用策略时在 warnings 中添加提示（Requirements 6.4）
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 5.2 实现 `extract(html: str, base_url: str) -> tuple[list[NewsItem], list[str]]`
    - 每个 NewsItem 标题非空（Requirements 3.2）
    - 每个 NewsItem 链接为绝对 URL，相对 URL 使用 base_url 解析（Requirements 3.3, 3.6）
    - 提取 section 字段，无则设为 None（Requirements 3.4, 3.5）
    - 无条目时返回空列表和警告（Requirements 3.7）
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x]* 5.3 在 `tests/test_extractor.py` 中为 `extract` 编写单元测试
    - 测试含 section 标签的 HTML 正确提取 section（Requirements 3.4, 3.5）
    - 测试无新闻条目时返回空列表和警告（Requirements 3.7）
    - 测试 BBC/CNN/Economist 各站点示例 HTML 提取正确（Requirements 6.1, 6.2）
    - 测试未知站点触发通用策略并含警告（Requirements 6.3, 6.4）
    - _Requirements: 3.4, 3.5, 3.7, 6.1, 6.2, 6.3, 6.4_

  - [x]* 5.4 在 `tests/test_extractor.py` 中编写属性测试 P3
    - **Property 3: All extracted NewsItems have non-empty title and absolute URL link**
    - **Validates: Requirements 3.2, 3.3**
    - 使用 Hypothesis 生成随机 HTML 结构，验证所有提取的 NewsItem 标题非空且链接为绝对 URL

  - [x]* 5.5 在 `tests/test_extractor.py` 中编写属性测试 P4
    - **Property 4: Relative URLs are resolved to absolute**
    - **Validates: Requirements 3.6**
    - 使用 Hypothesis 生成含相对链接的 HTML 和 base_url，验证提取后所有链接为绝对 URL

  - [x]* 5.6 在 `tests/test_extractor.py` 中编写属性测试 P7
    - **Property 7: Generic extraction strategy notice in warnings**
    - **Validates: Requirements 6.4**
    - 使用 Hypothesis 生成不匹配任何已知站点的 HTML，验证 warnings 包含通用策略提示

- [x] 6. 实现 Pretty_Printer
  - [x] 6.1 在 `news_homepage_parser/pretty_printer.py` 中实现 `to_json(result: ParseResult) -> str`
    - 序列化 ParseResult 为 JSON 字符串，包含 url、fetched_at、total、items、warnings 字段（Requirements 4.1, 4.3, 4.4）
    - `NewsItem.section` 为 None 时序列化为 `null`（Requirements 5.1）
    - _Requirements: 4.1, 4.3, 4.4, 5.1_

  - [x] 6.2 实现 `to_table(result: ParseResult) -> str`
    - 使用 `rich` 渲染含 title、link、section 列的格式化表格（Requirements 4.2）
    - 输出中包含 total、url、fetched_at 信息（Requirements 4.3, 4.4）
    - _Requirements: 4.2, 4.3, 4.4_

  - [x] 6.3 实现 `from_json(json_str: str) -> tuple[bool, list[NewsItem] | str]`
    - 从 JSON 字符串反序列化为 NewsItem 列表（Requirements 5.2）
    - JSON 格式非法时返回错误（Requirements 5.4）
    - _Requirements: 5.2, 5.4_

  - [x]* 6.4 在 `tests/test_pretty_printer.py` 中为 Pretty_Printer 编写单元测试
    - 测试 JSON 输出包含 total、url、fetched_at 字段（Requirements 4.3, 4.4）
    - 测试恶意 JSON 字符串反序列化返回错误（Requirements 5.4）
    - _Requirements: 4.3, 4.4, 5.4_

  - [x]* 6.5 在 `tests/test_pretty_printer.py` 中编写属性测试 P5
    - **Property 5: Table output contains all required columns and item data**
    - **Validates: Requirements 4.2**
    - 使用 Hypothesis 生成随机 NewsItem 列表，验证表格输出包含列头 title、link、section 及各条目数据

  - [x]* 6.6 在 `tests/test_pretty_printer.py` 中编写属性测试 P6
    - **Property 6: ParseResult round-trip serialization**
    - **Validates: Requirements 4.3, 4.4, 5.1, 5.2, 5.3**
    - 使用 Hypothesis 生成随机 ParseResult，序列化后反序列化，验证与原始对象等价

- [x] 7. Checkpoint — 确保所有测试通过
  - 运行 `pytest tests/test_extractor.py tests/test_pretty_printer.py`，确保全部通过，如有问题请告知。

- [x] 8. 实现顶层 Parser 与 CLI 入口
  - [x] 8.1 在 `news_homepage_parser/parser.py` 中实现 `parse(url: str, output_format: str = "json") -> ParseResult`
    - 串联 validate_url → fetch → extract → pretty_printer（Requirements 1.1, 2.1, 3.1, 4.1）
    - 使用 `try/except Exception` 兜底，捕获所有未处理异常并返回结构化错误（Requirements 7.1）
    - 使用 `logging` 模块记录错误（Requirements 7.2）
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 8.2 在 `news_homepage_parser/__main__.py` 中实现 CLI 入口
    - 接收 URL 参数和可选 `--format` 参数（json/table）
    - 调用 `parse()` 并打印结果
    - _Requirements: 1.1, 4.1, 4.2_

  - [x]* 8.3 在 `tests/test_integration.py` 中编写端到端集成测试（mock HTTP）
    - 测试组件抛出异常时顶层返回结构化错误（Requirements 7.1）
    - 测试完整流程：URL 验证 → 抓取 → 提取 → 输出（Requirements 1.1, 2.1, 3.1, 4.1）
    - _Requirements: 7.1, 7.2_

- [x] 9. Final Checkpoint — 确保所有测试通过
  - 运行 `pytest tests/`，确保全部通过，如有问题请告知。

## Notes

- 标有 `*` 的子任务为可选项，可跳过以加快 MVP 进度
- 每个任务均引用具体需求条款以保证可追溯性
- 属性测试使用 Hypothesis，每个属性对应设计文档中的一个 Correctness Property
- 单元测试与属性测试互补，前者覆盖具体示例，后者验证普遍性质
