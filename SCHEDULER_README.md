# 定时任务调度器使用说明

## 概述

本项目使用 APScheduler 实现定时抓取新闻数据的功能。所有启用的平台统一每天抓取 4 次（北京时间 00:00 / 06:00 / 12:00 / 18:00），抓取完成后自动触发 LLM 关键词分析。

## 配置说明

### 启用/禁用调度器

```python
# django_api/settings.py
SCHEDULER_ENABLED = True
SCHEDULER_TIMEZONE = 'Asia/Shanghai'
```

### 任务配置格式

```python
SCHEDULER_CONFIG = {
    'ftchinese': {
        'cron': '0 6,12,18,0 * * *',  # 每天 00/06/12/18 点
        'enabled': True,
    },
    'github_trending_daily': {
        'cron': '0 6,12,18,0 * * *',
        'enabled': True,
        'params': {'since': 'daily'},  # 额外参数
    },
}
```

### Cron 表达式格式

格式：`分 时 日 月 周`

| 示例 | 含义 |
|------|------|
| `0 6,12,18,0 * * *` | 每天 00/06/12/18 点（当前所有平台的配置）|
| `*/30 * * * *` | 每30分钟 |
| `0 */6 * * *` | 每6小时 |
| `0 8 * * *` | 每天8点 |

## 支持的平台

### ✅ 启用平台（每天 00:00 / 06:00 / 12:00 / 18:00）

**国内**

| 平台名 | 说明 | 抓取方式 |
|--------|------|---------|
| ftchinese | FT中文网 | Playwright |
| kr36 | 36氪 | Playwright |
| tmtpost | 钛媒体 | Playwright |
| jiqizhixin | 机器之心 | HTTP API |
| cls | 财联社 | HTTP + BS4 |
| wscn | 华尔街见闻 | HTTP API |
| huxiu | 虎嗅 | HTTP API |
| zaobao | 联合早报 | Playwright |
| zaobao_hotlist | 联合早报热榜 | HTTP API |
| zhihu | 知乎 | HTTP API |
| weibo | 微博 | HTTP API |
| pengpai | 澎湃新闻 | HTTP API |

**国际**

| 平台名 | 说明 | 抓取方式 |
|--------|------|---------|
| economist | The Economist | Playwright |
| apnews | AP News | Playwright |
| theverge | The Verge | Playwright |
| techcrunch | TechCrunch | Playwright |
| mittr | MIT Technology Review | Playwright |
| github_trending_daily/weekly/monthly | GitHub Trending | HTTP API |
| hacker_news | Hacker News | HTTP API |

### ❌ 禁用平台

| 平台名 | 禁用原因 |
|--------|---------|
| wsj | 需要付费订阅 |
| washingtonpost | 反爬较强 |
| keyword_analysis | 已弃用（被 LLM 方案取代）|
| keyword_analysis_llm（cron）| 改为由抓取完成后动态触发 |

## LLM 关键词分析触发

**不走固定 cron**，通过批次完成计数动态触发：

1. 批次开始时记录总任务数
2. 每个任务完成后计数 +1
3. 全部完成 → **延迟 5 分钟**自动触发 LLM 分析
4. 超过 **15 分钟**未完成 → 强制兜底触发

实际执行约在 00:15 / 06:15 / 12:15 / 18:15 前后。

## 使用方式

### 方式1：随 Django 应用启动（推荐）

```bash
.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

调度器随应用自动启动，日志示例：
```
[Scheduler] Task registered: ftchinese cron=0 6,12,18,0 * * *
[Scheduler] Scheduler started successfully with 21 tasks
```

### 方式2：独立运行调度器

```bash
.venv\Scripts\python.exe manage.py run_scheduler
```

### 方式3：手动触发所有任务

```bash
# 并行执行所有启用平台
.venv\Scripts\python.exe manage.py run_all_tasks --parallel

# 只执行指定平台
.venv\Scripts\python.exe manage.py run_all_tasks --platform ftchinese,kr36
```

## 监控

```bash
# 查看调度器状态和下次执行时间
curl http://localhost:8000/api/scheduler/status/

# 查看执行日志
tail -f logs/app.log | grep Scheduler

# 查看错误
grep ERROR logs/app.log
```

## 添加新平台步骤

1. 新增提取器：`news_homepage_parser/extractor/{platform}.py`
2. 注册到 `extractor/__init__.py` 域名分发
3. 新增视图函数：`parser_api/views.py`
4. 注册路由：`parser_api/urls.py`
5. 注册 view_map：`parser_api/scheduler.py`
6. 添加调度配置：`django_api/settings.py` `SCHEDULER_CONFIG`
7. 加入平台分组：`django_api/settings.py` `PLATFORM_GROUPS`
8. 添加标签：`parser_api/frontend_views.py` `PLATFORM_LABELS`

## 注意事项

- **任务不重叠**：`max_instances=1`，同一任务不会并发执行
- **数据库连接**：长时间运行时调用 `close_old_connections()` 防止超时
- **代理配置**：国际平台需要在 `.env` 中配置 `PLAYWRIGHT_PROXY`
- **date 精度**：写入时截断到分钟（`replace(second=0, microsecond=0)`），保证同批次 `MAX(date)` 精确匹配

## 生产部署

### Systemd

```ini
[Unit]
Description=News Scheduler Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/project
ExecStart=/path/to/project/.venv/bin/python manage.py run_scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable news-scheduler
sudo systemctl start news-scheduler
```

### Supervisor

```ini
[program:news-scheduler]
command=/path/to/.venv/bin/python manage.py run_scheduler
directory=/path/to/project
autostart=true
autorestart=true
```
