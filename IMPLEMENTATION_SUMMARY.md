# 定时任务实现总结

## 核心文件

| 文件 | 说明 |
|------|------|
| `parser_api/scheduler.py` | 调度器核心：任务注册、批次计数、LLM 动态触发 |
| `parser_api/apps.py` | Django 应用配置，随服务启动自动初始化调度器 |
| `parser_api/management/commands/run_all_tasks.py` | 手动一次性执行所有任务 |
| `parser_api/management/commands/run_scheduler.py` | 独立进程运行调度器 |
| `django_api/settings.py` | `SCHEDULER_CONFIG` 平台任务配置 |

---

## 已配置的任务

### ✅ 启用平台 — 每天 4 次（北京时间 00:00 / 06:00 / 12:00 / 18:00）

Cron 表达式：`0 6,12,18,0 * * *`

**国内平台**

| 平台 | 说明 | 抓取方式 |
|------|------|---------|
| ftchinese | FT中文网 | Playwright |
| kr36 | 36氪 | Playwright |
| tmtpost | 钛媒体 | Playwright |
| jiqizhixin | 机器之心 | HTTP API |
| cls | 财联社 | HTTP + BeautifulSoup |
| wscn | 华尔街见闻 | HTTP API |
| huxiu | 虎嗅 | HTTP API（绕过阿里云WAF）|
| zaobao | 联合早报 | Playwright |
| zaobao_hotlist | 联合早报热榜 | HTTP API |
| zhihu | 知乎 | HTTP API |
| weibo | 微博 | HTTP API |
| pengpai | 澎湃新闻 | HTTP API |

**国际平台**

| 平台 | 说明 | 抓取方式 |
|------|------|---------|
| economist | The Economist | Playwright |
| apnews | AP News | Playwright |
| theverge | The Verge | Playwright |
| techcrunch | TechCrunch | Playwright |
| mittr | MIT Technology Review | Playwright + 正则解析内联JSON |
| github_trending_daily | GitHub Trending 日榜 | HTTP API |
| github_trending_weekly | GitHub Trending 周榜 | HTTP API |
| github_trending_monthly | GitHub Trending 月榜 | HTTP API |
| hacker_news | Hacker News | HTTP API |

### ❌ 禁用平台

| 平台 | 禁用原因 |
|------|---------|
| wsj | cn.wsj.com 需要付费订阅，RSS 已关闭 |
| washingtonpost | 反爬较强，需要进一步调试 |
| keyword_analysis | 已弃用，被 LLM 两阶段方案取代 |
| keyword_analysis_llm（cron） | 改为由抓取完成后动态触发，不走固定时间 |

---

## LLM 关键词分析触发机制

**不走固定 cron**，通过批次完成计数动态触发：

1. 每批抓取开始时记录总任务数
2. 每个抓取任务完成后计数 +1
3. 当 done == total 时，**延迟 5 分钟**自动注入 LLM 分析任务
4. 若 15 分钟后 LLM 分析仍未触发（某任务卡死），**强制执行兜底**

实际执行时间约为 00:15、06:15、12:15、18:15 前后。

---

## 常用命令

```powershell
# 启动后端（含调度器）
.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000

# 手动执行所有平台（并行）
.venv\Scripts\python.exe manage.py run_all_tasks --parallel

# 手动执行指定平台
.venv\Scripts\python.exe manage.py run_all_tasks --platform ftchinese,kr36

# 手动触发 LLM 关键词分析
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --group domestic --force
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --group international --force

# 只跑阶段2（复用缓存的阶段1结果）
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --stage2-only --group domestic

# 查看调度器状态
curl http://localhost:8000/api/scheduler/status/
```

---

## 功能特性

- **任务不重叠**：`max_instances=1`，同一任务不会并发执行
- **统一频率**：所有平台每天4次，保证热点分析数据新鲜度一致
- **异常隔离**：单个平台失败不影响其他平台和后续 LLM 分析
- **数据库连接**：每次任务执行前调用 `close_old_connections()` 防止长连接超时
- **日志完整**：每个任务记录开始时间、耗时、成功/失败状态
