# 定时任务快速参考

## 三种运行方式对比

| 命令 | 用途 | 执行方式 | 适用场景 |
|------|------|---------|---------|
| `runserver` | 开发环境 | 随应用启动，后台自动执行 | 本地开发 |
| `run_scheduler` | 生产环境 | 独立进程，持续运行 | 服务器部署 |
| `run_all_tasks` | 手动触发 | 立即执行一次后退出 | 测试、初始化 |

## 常用命令

```bash
# 1. 开发环境 - 启动应用（调度器自动启动）
./.venv/Scripts/python manage.py runserver

# 2. 生产环境 - 独立运行调度器
./.venv/Scripts/python manage.py run_scheduler

# 3. 立即执行所有任务（顺序）
./.venv/Scripts/python manage.py run_all_tasks

# 4. 立即执行所有任务（并行，更快）
./.venv/Scripts/python manage.py run_all_tasks --parallel

# 5. 只执行指定平台
./.venv/Scripts/python manage.py run_all_tasks --platform weibo,zhihu

# 6. 查看调度器状态
curl http://localhost:8000/api/scheduler/status/

# 7. 查看日志
tail -f logs/app.log | grep Scheduler
```

## 配置文件位置

```
django_api/settings.py
├── SCHEDULER_ENABLED = True          # 启用/禁用
├── SCHEDULER_TIMEZONE = 'Asia/Shanghai'  # 时区
└── SCHEDULER_CONFIG = {              # 任务配置
        'weibo': {
            'cron': '*/30 * * * *',   # cron 表达式
            'enabled': True,          # 启用/禁用
        },
    }
```

## Cron 表达式速查

```
格式: 分 时 日 月 周

*/30 * * * *    每30分钟
0 */6 * * *     每6小时（0点、6点、12点、18点）
0 8 * * *       每天8点
0 0 * * 0       每周日0点
0 0 1 * *       每月1号0点
```

## 14个平台默认配置

| 平台 | 频率 | Cron |
|------|------|------|
| economist | 每6小时 | `0 */6 * * *` |
| apnews | 每4小时 | `0 */4 * * *` |
| ftchinese | 每30分钟 | `*/30 * * * *` |
| wsj | 每4小时 | `0 */4 * * *` |
| kr36 | 每30分钟 | `*/30 * * * *` |
| huxiu | 每30分钟 | `*/30 * * * *` |
| zaobao | 每4小时 | `0 */4 * * *` |
| zaobao_hotlist | 每30分钟 | `*/30 * * * *` |
| github_trending | 每6小时 | `0 */6 * * *` |
| hacker_news | 每30分钟 | `*/30 * * * *` |
| zhihu | 每30分钟 | `*/30 * * * *` |
| weibo | 每30分钟 | `*/30 * * * *` |
| pengpai | 每30分钟 | `*/30 * * * *` |
| washingtonpost | 每6小时 | `0 */6 * * *` |

## 快速操作

### 禁用某个任务

编辑 `django_api/settings.py`：

```python
'weibo': {
    'cron': '*/30 * * * *',
    'enabled': False,  # 改为 False
},
```

### 修改执行频率

```python
'weibo': {
    'cron': '*/15 * * * *',  # 改为每15分钟
    'enabled': True,
},
```

### 添加新任务

```python
'new_platform': {
    'cron': '0 */2 * * *',  # 每2小时
    'enabled': True,
    'params': {'key': 'value'},  # 可选参数
},
```

## 故障排查

```bash
# 1. 检查调度器是否启动
curl http://localhost:8000/api/scheduler/status/

# 2. 查看错误日志
grep ERROR logs/app.log

# 3. 查看任务执行日志
grep "Scheduler" logs/app.log

# 4. 测试单个平台
./.venv/Scripts/python manage.py run_all_tasks --platform weibo

# 5. 检查配置
./.venv/Scripts/python -c "from django.conf import settings; print(settings.SCHEDULER_CONFIG)"
```

## 性能对比

| 执行方式 | 14个任务耗时 | 说明 |
|---------|------------|------|
| 顺序执行 | ~120秒 | 稳定，适合调试 |
| 并行执行 | ~35秒 | 快速，适合生产 |
| 单个任务 | 1-12秒 | 取决于平台 |

## 生产环境部署

### Systemd 服务

```bash
# 创建服务文件
sudo nano /etc/systemd/system/news-scheduler.service

# 启动服务
sudo systemctl enable news-scheduler
sudo systemctl start news-scheduler
sudo systemctl status news-scheduler
```

### Supervisor 配置

```ini
[program:news-scheduler]
command=/path/to/.venv/bin/python manage.py run_scheduler
directory=/path/to/project
autostart=true
autorestart=true
```

### Cron 定时执行

```bash
# 每6小时执行一次全量抓取
0 */6 * * * cd /path/to/project && ./.venv/bin/python manage.py run_all_tasks --parallel
```

## 监控建议

1. 定期检查日志文件大小
2. 监控任务执行成功率
3. 设置失败告警
4. 监控数据库连接数
5. 跟踪任务执行耗时

## 文档链接

- 详细使用说明：`SCHEDULER_README.md`
- run_all_tasks 指南：`RUN_ALL_TASKS_GUIDE.md`
- 实现总结：`IMPLEMENTATION_SUMMARY.md`
