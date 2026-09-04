# run_all_tasks 命令使用指南

## 概述

`run_all_tasks` 立即执行所有已启用平台的抓取任务一次，执行完成后退出。适用于：

- 🧪 **测试**：验证所有抓取接口是否正常
- 🔄 **手动触发**：立即更新数据
- 📊 **初始化**：首次部署填充数据库
- 🐛 **调试**：排查特定平台问题

## 基本用法

```powershell
# 顺序执行所有启用的任务
.venv\Scripts\python.exe manage.py run_all_tasks

# 并行执行（推荐，速度提升 3-4 倍）
.venv\Scripts\python.exe manage.py run_all_tasks --parallel

# 只执行指定平台
.venv\Scripts\python.exe manage.py run_all_tasks --platform ftchinese,kr36

# 并行 + 指定平台
.venv\Scripts\python.exe manage.py run_all_tasks --platform ftchinese,kr36 --parallel

# 包含 LLM 关键词分析（默认排除，因耗时较长）
.venv\Scripts\python.exe manage.py run_all_tasks --parallel --include-all
```

## 支持的平台名称

**国内平台**

| 平台名 | 说明 | 平均耗时 |
|--------|------|---------|
| ftchinese | FT中文网 | 10-15s（Playwright）|
| kr36 | 36氪 | 10-15s（Playwright）|
| tmtpost | 钛媒体 | 15-20s（Playwright）|
| jiqizhixin | 机器之心 | <1s（API）|
| cls | 财联社 | <1s（HTTP）|
| wscn | 华尔街见闻 | <1s（API）|
| huxiu | 虎嗅 | <1s（API）|
| zaobao | 联合早报 | 10-15s（Playwright）|
| zaobao_hotlist | 联合早报热榜 | 2-3s |
| zhihu | 知乎 | 1-2s |
| weibo | 微博 | 2-3s |
| pengpai | 澎湃新闻 | 1-2s |

**国际平台**（需配置代理）

| 平台名 | 说明 | 平均耗时 |
|--------|------|---------|
| economist | The Economist | 20-30s（Playwright）|
| apnews | AP News | 15-20s（Playwright）|
| theverge | The Verge | 20-30s（Playwright）|
| techcrunch | TechCrunch | 10-15s（Playwright）|
| mittr | MIT Technology Review | 10-15s（Playwright）|
| github_trending_daily | GitHub 日榜 | 5-10s |
| github_trending_weekly | GitHub 周榜 | 5-10s |
| github_trending_monthly | GitHub 月榜 | 5-10s |
| hacker_news | Hacker News | 2-3s |

## 性能对比

| 执行方式 | 全部任务耗时 | 说明 |
|---------|------------|------|
| 顺序执行 | ~3-5 分钟 | 稳定，适合调试 |
| 并行执行 | ~1-2 分钟 | 最多5并发，适合生产 |

## 默认排除

`keyword_analysis_llm` 默认被排除（耗时 5-20 分钟），需单独运行：

```powershell
# 国内热点 LLM 分析
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --group domestic --force

# 国际热点 LLM 分析
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --group international --force
```

## 与 run_scheduler 的区别

| 特性 | run_all_tasks | run_scheduler |
|------|--------------|---------------|
| 执行方式 | 立即执行一次后退出 | 持续运行，按计划执行 |
| 适用场景 | 手动触发、测试、初始化 | 生产环境长期运行 |
| 进程类型 | 短期任务 | 守护进程 |

## 常见问题

### Q: 某个平台失败，其他平台会继续吗？

A: 会。单个任务失败不影响其他任务，最终统计会显示失败数量。

### Q: 国际平台一直失败？

A: 检查 `.env` 中的 `PLAYWRIGHT_PROXY` 是否配置正确。

### Q: 后台执行

```powershell
# PowerShell 后台执行
Start-Job { Set-Location d:\source\info; .venv\Scripts\python.exe manage.py run_all_tasks --parallel }
```
