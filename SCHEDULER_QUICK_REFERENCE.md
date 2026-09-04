# 定时任务快速参考

## 三种运行方式

| 命令 | 用途 | 适用场景 |
|------|------|---------|
| `runserver` | 随应用启动，调度器自动运行 | 本地开发 |
| `run_scheduler` | 独立进程持续运行 | 服务器生产部署 |
| `run_all_tasks` | 立即执行一次后退出 | 手动触发、初始化、调试 |

## 常用命令

```powershell
# 启动后端（含调度器）
.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000

# 独立运行调度器
.venv\Scripts\python.exe manage.py run_scheduler

# 立即执行所有任务（并行）
.venv\Scripts\python.exe manage.py run_all_tasks --parallel

# 执行指定平台
.venv\Scripts\python.exe manage.py run_all_tasks --platform ftchinese,kr36

# 手动触发 LLM 关键词分析
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --group domestic --force
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --group international --force

# 只跑 LLM 阶段2（复用缓存）
.venv\Scripts\python.exe manage.py extract_keywords_llm --v2 --stage2-only --group domestic

# 查看调度器状态
curl http://localhost:8000/api/scheduler/status/

# 查看日志
tail -f logs/app.log | grep Scheduler
```

## 所有平台执行时间

所有启用平台统一：**每天 00:00 / 06:00 / 12:00 / 18:00（北京时间）**

Cron 表达式：`0 6,12,18,0 * * *`

**国内（12个）**：ftchinese、kr36、tmtpost、jiqizhixin、cls、wscn、huxiu、zaobao、zaobao_hotlist、zhihu、weibo、pengpai

**国际（9个）**：economist、apnews、theverge、techcrunch、mittr、github_trending_daily/weekly/monthly、hacker_news

**LLM 分析**：所有抓取完成后延迟 5 分钟自动触发（约 00:15 / 06:15 / 12:15 / 18:15）

## 禁用平台

| 平台 | 原因 |
|------|------|
| wsj | 需要付费订阅 |
| washingtonpost | 反爬较强 |

## 快速操作

### 禁用平台

```python
# django_api/settings.py
'weibo': {
    'cron': '0 6,12,18,0 * * *',
    'enabled': False,  # 改为 False
},
```

### 修改执行时间

```python
'ftchinese': {
    'cron': '0 */2 * * *',  # 改为每2小时
    'enabled': True,
},
```

## Cron 表达式速查

| 表达式 | 含义 |
|--------|------|
| `0 6,12,18,0 * * *` | 每天 00/06/12/18 点 |
| `*/30 * * * *` | 每30分钟 |
| `0 */6 * * *` | 每6小时 |
| `0 8 * * *` | 每天8点 |
| `0 0 * * 0` | 每周日0点 |

## 故障排查

```powershell
# 检查调度器是否正常运行
curl http://localhost:8000/api/scheduler/status/

# 查看错误日志
Select-String -Path logs/app.log -Pattern "ERROR"

# 测试单个平台
.venv\Scripts\python.exe manage.py run_all_tasks --platform weibo
```

## 文档链接

- 详细说明：`SCHEDULER_README.md`
- 实现总结：`IMPLEMENTATION_SUMMARY.md`
- 命令手册：`COMMANDS.md`
- run_all_tasks 指南：`RUN_ALL_TASKS_GUIDE.md`
