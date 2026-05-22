# Implementation Plan: django-api-wrapper

## Overview

将 `news_homepage_parser` 包封装为 Django Web 服务，暴露 `GET /economist/` REST API 端点。采用零侵入原则，不修改现有包代码，通过新增 `django_api/` 项目配置包和 `parser_api/` Django app 实现。

## Tasks

- [x] 1. 添加 Django 依赖并初始化项目结构
  - 在 `requirements.txt` 末尾追加 `django`
  - 创建 `django_api/__init__.py`、`parser_api/__init__.py` 空文件
  - _Requirements: 1.1, 4.1_

- [x] 2. 实现 Django 项目配置
  - [x] 2.1 创建 `django_api/settings.py`
    - 最小化配置：`SECRET_KEY`、`DEBUG=True`、`INSTALLED_APPS`（含 `parser_api`）、`ROOT_URLCONF='django_api.urls'`、SQLite 默认数据库
    - _Requirements: 1.1, 1.3_
  - [x] 2.2 创建 `django_api/urls.py`
    - 根路由通过 `include('parser_api.urls')` 转发所有请求
    - _Requirements: 1.1_
  - [x] 2.3 创建 `django_api/wsgi.py`
    - 标准 WSGI 入口，`DJANGO_SETTINGS_MODULE='django_api.settings'`
    - _Requirements: 1.1_
  - [x] 2.4 创建 `manage.py`
    - 标准 Django manage.py，指向 `django_api.settings`
    - _Requirements: 1.1_

- [x] 3. 实现 parser_api app
  - [x] 3.1 创建 `parser_api/site_config.py`
    - 定义 `SITE_URLS` 字典，初始包含 `"economist": "https://www.economist.com"`
    - _Requirements: 2.1_
  - [x] 3.2 创建 `parser_api/urls.py`
    - 定义 `urlpatterns`，包含 `path("economist/", views.economist_view)`
    - _Requirements: 2.1, 2.5_
  - [x] 3.3 实现 `parser_api/views.py` 中的 `_parse_site_view()` 辅助函数
    - 仅接受 GET 方法（非 GET 返回 405）
    - 调用 `parse(url)`，捕获未捕获异常返回 500
    - 根据 `result.error` 决定状态码（None→200，非空→502）
    - 返回 `HttpResponse(to_json(result), content_type="application/json", status=...)`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 3.4 实现 `parser_api/views.py` 中的 `economist_view()` 视图函数
    - 调用 `_parse_site_view(request, SITE_URLS["economist"])`
    - _Requirements: 2.1_

- [x] 4. Checkpoint — 确认项目结构完整
  - 确认所有文件已创建，`python manage.py check` 应无错误，如有问题请告知。

- [ ] 5. 编写单元测试
  - [x] 5.1 创建 `tests/test_django_api.py`，配置 Django 测试环境
    - 在文件顶部设置 `DJANGO_SETTINGS_MODULE`，使用 `django.test.Client`
    - _Requirements: 1.2_
  - [x] 5.2 编写路由解析单元测试
    - 验证 `/economist/` 路由解析到 `economist_view`
    - _Requirements: 1.1, 2.1_
  - [x] 5.3 编写 `parse()` 抛出异常时返回 500 的单元测试
    - mock `parser_api.views.parse` 抛出 `RuntimeError`，断言状态码为 500
    - _Requirements: 2.4_
  - [x]* 5.4 编写非 GET 方法返回 405 的单元测试
    - 对 POST、PUT、DELETE 分别断言状态码为 405
    - _Requirements: 2.5_

- [ ] 6. 编写属性测试（Hypothesis）
  - [ ]* 6.1 实现 Property 1：HTTP 状态码与 ParseResult.error 一致
    - 生成随机 `ParseResult`，`error` 随机为 `None` 或非空字符串
    - mock `parse()` 返回该对象，断言状态码 200（error=None）或 502（error 非空）
    - `settings(max_examples=100)`
    - `# Feature: django-api-wrapper, Property 1: HTTP status matches ParseResult.error`
    - _Requirements: 2.2, 2.3_
  - [ ]* 6.2 实现 Property 2：非 GET 方法返回 405
    - 从 POST/PUT/DELETE/PATCH/HEAD/OPTIONS 中采样 HTTP 方法
    - 断言状态码为 405
    - `# Feature: django-api-wrapper, Property 2: non-GET methods return 405`
    - _Requirements: 2.5_
  - [ ]* 6.3 实现 Property 3：API 响应体与 to_json() 输出等价（Round-trip）
    - 生成随机 `ParseResult`（含随机 `NewsItem` 列表、`most_read`、`warnings`、`error`）
    - 比较 `json.loads(response.content)` 与 `json.loads(to_json(result))`
    - `# Feature: django-api-wrapper, Property 3: API response equals to_json() output`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  - [ ]* 6.4 实现 Property 4：Content-Type 始终为 application/json
    - 覆盖成功和错误两种 ParseResult
    - 断言响应头 `Content-Type` 包含 `application/json`
    - `# Feature: django-api-wrapper, Property 4: Content-Type is always application/json`
    - _Requirements: 2.2_

- [x] 7. Final Checkpoint — 确保所有测试通过
  - 确保所有测试通过，如有问题请告知。

## Notes

- 标有 `*` 的子任务为可选项，可跳过以加快 MVP 进度
- 每个任务引用具体需求条款以保证可追溯性
- 属性测试使用 `hypothesis` 库（已在 requirements.txt 中声明）
- 单元测试和属性测试均使用 `django.test.Client`，无需启动真实服务器
- `parse()` 内部已捕获所有异常写入 `result.error`，500 路径仅作防御性兜底
