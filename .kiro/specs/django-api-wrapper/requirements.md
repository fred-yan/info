# Requirements Document

## Introduction

将现有的 `news_homepage_parser` Python 包封装为一个 Django Web 服务，暴露一个 REST API 端点。该端点接收 GET 请求，调用现有的解析逻辑（Playwright 抓取 + HTML 提取），并以 JSON 格式返回结构化的新闻首页数据。初期仅支持 The Economist 首页解析。

## Glossary

- **Django_App**: 基于 Django 框架构建的 Web 应用服务，监听 `http://127.0.0.1:8000`
- **API_Endpoint**: HTTP 接口，路径为 `/economist/`，接受 GET 请求
- **Parser**: 现有 `news_homepage_parser` 包中的 `parse()` 函数，负责抓取并解析新闻首页
- **ParseResult**: `news_homepage_parser.models.ParseResult` 数据类，包含 `url`、`fetched_at`、`total`、`sections`、`most_read`、`warnings`、`error` 字段
- **JSON_Response**: 由 `pretty_printer.to_json()` 序列化的 JSON 字符串，作为 HTTP 响应体返回
- **Client**: 向 API_Endpoint 发送 HTTP 请求的调用方

## Requirements

### Requirement 1: Django 项目初始化

**User Story:** As a developer, I want a minimal Django project scaffold, so that I can run the API server with a single command.

#### Acceptance Criteria

1. THE Django_App SHALL include一个 Django 项目配置（`settings.py`），使其可通过 `python manage.py runserver` 启动
2. THE Django_App SHALL 将 `news_homepage_parser` 包注册为可导入模块，无需修改现有包代码
3. THE Django_App SHALL 使用 SQLite 作为默认数据库（Django 默认值），无需额外配置

---

### Requirement 2: Economist 首页解析端点

**User Story:** As a client, I want to call `GET /economist/` and receive parsed news data, so that I can consume structured news content programmatically.

#### Acceptance Criteria

1. WHEN THE Client 发送 `GET /economist/` 请求，THE API_Endpoint SHALL 调用 `Parser` 解析 `https://www.economist.com` 并返回 JSON_Response
2. WHEN THE Parser 成功返回 ParseResult，THE API_Endpoint SHALL 以 HTTP 200 状态码和 `Content-Type: application/json` 返回 JSON_Response
3. WHEN THE Parser 返回的 ParseResult 包含非空 `error` 字段，THE API_Endpoint SHALL 以 HTTP 502 状态码返回包含 `error` 字段的 JSON_Response
4. IF THE Parser 抛出未捕获异常，THEN THE API_Endpoint SHALL 以 HTTP 500 状态码返回包含 `error` 字段的 JSON_Response
5. THE API_Endpoint SHALL 仅接受 GET 方法；WHEN 收到其他 HTTP 方法，THE API_Endpoint SHALL 返回 HTTP 405 状态码

---

### Requirement 3: JSON 响应格式一致性

**User Story:** As a client, I want the API response to match the existing script output format, so that I don't need to change my downstream data processing logic.

#### Acceptance Criteria

1. THE JSON_Response SHALL 包含以下顶层字段：`url`、`fetched_at`、`total`、`sections`、`most_read`、`warnings`、`error`
2. THE JSON_Response 中的 `sections` 字段 SHALL 为数组，每个元素包含 `section`（字符串）和 `articles`（数组）字段
3. THE JSON_Response 中每篇文章 SHALL 包含 `title`、`link`、`section` 字段
4. THE JSON_Response 中的 `most_read` 字段 SHALL 为数组，每个元素包含 `title`、`link`、`section` 字段
5. FOR ALL valid ParseResult objects，THE Django_App 通过 API 返回的 JSON SHALL 与直接调用 `to_json(parse(url))` 产生的输出在结构上等价（round-trip 一致性）

---

### Requirement 4: 依赖管理

**User Story:** As a developer, I want all new dependencies declared explicitly, so that the project can be reproduced in a clean environment.

#### Acceptance Criteria

1. THE Django_App SHALL 在 `requirements.txt` 中新增 `django` 依赖
2. THE Django_App SHALL 复用现有 `.venv` 虚拟环境，无需创建新的虚拟环境
