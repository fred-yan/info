# 定时任务调度器使用说明

## 概述

本项目使用 APScheduler 实现定时抓取新闻数据的功能。调度器支持类似 crontab 的配置格式，可以灵活配置每个平台的抓取频率。

## 配置说明

### 1. 启用/禁用调度器

在 `django_api/settings.py` 中设置：

```python
SCHEDULER_ENABLED = True  # True 启用，False 禁用
```

### 2. 配置时区

```python
SCHEDULER_TIMEZONE = 'Asia/Shanghai'  # 设置调度器时区
```

### 3. 配置定时任务

在 `SCHEDULER_CONFIG` 中配置各平台的抓取任务：

```python
SCHEDULER_CONFIG = {
    'economist': {
        'cron': '0 */6 * * *',  # cron 表达式
        'enabled': True,         # 是否启用此任务
    },
    'zaobao_hotlist': {
        'cron': '*/30 * * * *',
        'enabled': True,
        'params': {'since': 'day'},  # 额外参数
    },
}
```

### Cron 表达式格式

格式：`分 时 日 月 周`

示例：
- `*/30 * * * *` - 每30分钟执行一次
- `0 */6 * * *` - 每6小时执行一次（0点、6点、12点、18点）
- `0 8 * * *` - 每天8点执行
- `0 0 * * 0` - 每周日0点执行
- `0 0 1 * *` - 每月1号0点执行

字段说明：
- 分钟：0-59
- 小时：0-23
- 日：1-31
- 月：1-12
- 周：0-6（0表示周日）

特殊字符：
- `*` - 任意值
- `*/n` - 每n个单位
- `n-m` - 范围
- `n,m` - 列表

## 使用方式

### 方式1：随 Django 应用启动（推荐）

调度器会在 Django 应用启动时自动初始化：

```bash
./.venv/Scripts/python manage.py runserver
```

启动后会看到类似日志：
```
[ParserApiConfig] Scheduler initialized
[Scheduler] Task registered: economist cron=0 */6 * * *
[Scheduler] Task registered: weibo cron=*/30 * * * *
[Scheduler] Scheduler started successfully with 14 tasks
```

### 方式2：独立运行调度器

适合在生产环境中作为独立进程运行：

```bash
./.venv/Scripts/python manage.py run_scheduler
```

输出示例：
```
Starting scheduler...
Scheduler is running. Press Ctrl+C to exit.

Registered 14 tasks:
  - Fetch economist: next run at 2026-03-09 18:00:00
  - Fetch weibo: next run at 2026-03-09 14:30:00
  - Fetch zhihu: next run at 2026-03-09 14:30:00
  ...
```

按 `Ctrl+C` 可优雅停止调度器。

### 方式3：立即执行所有任务一次

适合手动触发全量抓取或测试：

```bash
# 执行所有启用的任务
./.venv/Scripts/python manage.py run_all_tasks

# 只执行指定平台的任务
./.venv/Scripts/python manage.py run_all_tasks --platform weibo,zhihu

# 并行执行（更快，但占用更多资源）
./.venv/Scripts/python manage.py run_all_tasks --parallel
```

输出示例：
```
Running 14 tasks...

[1/14] Running: economist
  ✓ Completed in 5.2s

[2/14] Running: weibo
  ✓ Completed in 3.8s

...

============================================================
Total: 14 tasks
Success: 13
Failed: 1
Total time: 125.3s
============================================================
```

## 监控和管理

### 查看调度器状态

访问 API 端点：

```bash
curl http://localhost:8000/api/scheduler/status/
```

返回示例：
```json
{
  "status": "running",
  "timezone": "Asia/Shanghai",
  "jobs": [
    {
      "id": "fetch_economist",
      "name": "Fetch economist",
      "next_run": "2026-03-09T18:00:00+08:00",
      "trigger": "cron[hour='*/6', minute='0']"
    },
    {
      "id": "fetch_weibo",
      "name": "Fetch weibo",
      "next_run": "2026-03-09T14:30:00+08:00",
      "trigger": "cron[minute='*/30']"
    }
  ]
}
```

### 查看执行日志

日志会输出到 `logs/app.log`，可以查看任务执行情况：

```bash
tail -f logs/app.log | grep Scheduler
```

日志示例：
```
[2026-03-09 14:30:00] [INFO] [parser_api.scheduler] [Scheduler] Starting task: weibo
[2026-03-09 14:30:05] [INFO] [parser_api.scheduler] [Scheduler] Task completed: weibo (elapsed=5.2s)
```

## 支持的平台

当前配置支持以下平台的定时抓取：

| 平台 | 默认频率 | 说明 |
|------|---------|------|
| economist | 每6小时 | The Economist |
| apnews | 每4小时 | AP News |
| ftchinese | 每30分钟 | FT中文网 |
| wsj | 每4小时 | 华尔街日报中文网 |
| kr36 | 每30分钟 | 36氪 |
| huxiu | 每30分钟 | 虎嗅 |
| zaobao | 每4小时 | 早报首页 |
| zaobao_hotlist | 每30分钟 | 早报热榜 |
| github_trending | 每6小时 | GitHub Trending |
| hacker_news | 每30分钟 | Hacker News |
| zhihu | 每30分钟 | 知乎热榜 |
| weibo | 每30分钟 | 微博热搜 |
| pengpai | 每30分钟 | 澎湃新闻 |
| washingtonpost | 每6小时 | Washington Post |

## 调整配置

### 修改抓取频率

编辑 `django_api/settings.py` 中的 `SCHEDULER_CONFIG`，修改对应平台的 `cron` 值：

```python
'weibo': {
    'cron': '*/15 * * * *',  # 改为每15分钟
    'enabled': True,
},
```

### 禁用某个平台

将 `enabled` 设置为 `False`：

```python
'economist': {
    'cron': '0 */6 * * *',
    'enabled': False,  # 禁用
},
```

### 添加新平台

1. 在 `SCHEDULER_CONFIG` 中添加配置
2. 在 `parser_api/scheduler.py` 的 `view_map` 中添加对应的 view 函数映射

## 注意事项

1. **任务不重叠**：每个任务设置了 `max_instances=1`，确保同一任务不会重叠执行
2. **时区设置**：确保 `SCHEDULER_TIMEZONE` 与你的服务器时区一致
3. **数据库连接**：长时间运行时注意 MySQL 连接超时问题
4. **日志监控**：定期检查日志文件，确保任务正常执行
5. **资源占用**：根据服务器性能调整任务频率，避免过于频繁

## 故障排查

### 调度器未启动

检查：
1. `SCHEDULER_ENABLED` 是否为 `True`
2. 查看日志中是否有错误信息
3. 确认 apscheduler 已正确安装

### 任务未执行

检查：
1. 任务的 `enabled` 是否为 `True`
2. cron 表达式是否正确
3. 查看日志中的错误信息

### 任务执行失败

查看日志中的详细错误信息：
```bash
grep "Task error" logs/app.log
```

## 生产环境部署建议

1. **使用独立进程**：使用 `run_scheduler` 命令独立运行调度器
2. **进程管理**：使用 systemd 或 supervisor 管理调度器进程
3. **监控告警**：配置日志监控和告警机制
4. **资源限制**：根据实际情况调整任务频率和并发数

### Systemd 配置示例

创建 `/etc/systemd/system/news-scheduler.service`：

```ini
[Unit]
Description=News Scheduler Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/project/.venv/bin/python manage.py run_scheduler
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl enable news-scheduler
sudo systemctl start news-scheduler
sudo systemctl status news-scheduler
```
