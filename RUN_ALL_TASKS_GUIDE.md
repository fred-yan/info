# run_all_tasks 命令使用指南

## 概述

`run_all_tasks` 命令用于立即执行所有配置的任务一次，执行完成后自动退出。这对于以下场景非常有用：

- 🧪 **测试**：验证所有抓取接口是否正常工作
- 🔄 **手动触发**：需要立即更新所有数据
- 📊 **数据初始化**：首次部署时填充数据库
- 🐛 **调试**：排查特定平台的问题

## 基本用法

### 1. 执行所有任务（顺序执行）

```bash
./.venv/Scripts/python manage.py run_all_tasks
```

**特点**：
- 按顺序逐个执行任务
- 显示每个任务的执行进度和耗时
- 适合调试和查看详细输出

**输出示例**：
```
Running 14 tasks...

[1/14] Running: economist
  ✓ Completed in 5.2s

[2/14] Running: apnews
  ✓ Completed in 3.8s

[3/14] Running: ftchinese
  ✓ Completed in 2.1s

...

[14/14] Running: washingtonpost
  ✓ Completed in 4.5s

============================================================
Total: 14 tasks
Success: 14
Total time: 125.3s
============================================================
```

### 2. 执行所有任务（并行执行）

```bash
./.venv/Scripts/python manage.py run_all_tasks --parallel
```

**特点**：
- 同时执行多个任务（最多5个并发）
- 速度更快，但输出顺序不固定
- 适合生产环境快速更新数据

**输出示例**：
```
Running 14 tasks in parallel...

  ✓ pengpai completed
  ✓ zhihu completed
  ✓ weibo completed
  ✓ ftchinese completed
  ✓ kr36 completed
  ...

============================================================
Total: 14 tasks
Success: 14
Total time: 35.7s
============================================================
```

**性能对比**：
- 顺序执行：约 120-150 秒
- 并行执行：约 30-50 秒（提速 3-4 倍）

### 3. 只执行指定平台

```bash
# 执行单个平台
./.venv/Scripts/python manage.py run_all_tasks --platform weibo

# 执行多个平台（逗号分隔）
./.venv/Scripts/python manage.py run_all_tasks --platform weibo,zhihu,pengpai
```

**用途**：
- 测试特定平台
- 只更新某些数据源
- 调试问题平台

**输出示例**：
```
Running 3 tasks...

[1/3] Running: weibo
  ✓ Completed in 2.3s

[2/3] Running: zhihu
  ✓ Completed in 1.8s

[3/3] Running: pengpai
  ✓ Completed in 1.5s

============================================================
Total: 3 tasks
Success: 3
Total time: 5.6s
============================================================
```

### 4. 组合使用

```bash
# 并行执行指定平台
./.venv/Scripts/python manage.py run_all_tasks --platform weibo,zhihu,pengpai --parallel
```

### 5. 排除特定任务

```bash
# 额外排除某些任务
./.venv/Scripts/python manage.py run_all_tasks --exclude hacker_news,keyword_analysis

# 包含所有任务（忽略默认排除规则）
./.venv/Scripts/python manage.py run_all_tasks --include-all
```

**默认排除**：`keyword_analysis_llm`（LLM 关键词分析耗时过长，应单独运行）

**单独运行 LLM 关键词分析**：
```bash
./.venv/Scripts/python manage.py extract_keywords_llm
```

## 支持的平台列表

可以使用以下平台名称：

| 平台名称 | 说明 | 平均耗时 |
|---------|------|---------|
| economist | The Economist | 5-8秒 |
| apnews | AP News | 3-5秒 |
| ftchinese | FT中文网 | 2-3秒 |
| wsj | 华尔街日报中文网 | 3-5秒 |
| kr36 | 36氪 | 2-3秒 |
| huxiu | 虎嗅 | 2-3秒 |
| zaobao | 早报首页 | 3-4秒 |
| zaobao_hotlist | 早报热榜 | 1-2秒 |
| github_trending | GitHub Trending | 4-6秒 |
| hacker_news | Hacker News | 8-12秒 |
| zhihu | 知乎热榜 | 1-2秒 |
| weibo | 微博热搜 | 2-3秒 |
| pengpai | 澎湃新闻 | 1-2秒 |
| washingtonpost | Washington Post | 4-6秒 |

## 使用场景

### 场景1：首次部署初始化数据

```bash
# 并行执行所有任务，快速填充数据库
./.venv/Scripts/python manage.py run_all_tasks --parallel
```

### 场景2：测试所有接口

```bash
# 顺序执行，查看每个接口的详细输出
./.venv/Scripts/python manage.py run_all_tasks
```

### 场景3：调试特定平台问题

```bash
# 只执行有问题的平台
./.venv/Scripts/python manage.py run_all_tasks --platform weibo
```

### 场景4：定期手动更新热门数据

```bash
# 只更新高频数据源
./.venv/Scripts/python manage.py run_all_tasks --platform weibo,zhihu,pengpai,hacker_news --parallel
```

### 场景5：在 cron 中定时执行

```bash
# 添加到 crontab
0 */6 * * * cd /path/to/project && ./.venv/bin/python manage.py run_all_tasks --parallel >> /var/log/news-fetch.log 2>&1
```

## 与 run_scheduler 的区别

| 特性 | run_all_tasks | run_scheduler |
|------|--------------|---------------|
| 执行方式 | 立即执行一次后退出 | 持续运行，按计划自动执行 |
| 适用场景 | 手动触发、测试、初始化 | 生产环境长期运行 |
| 进程类型 | 短期任务 | 守护进程 |
| 资源占用 | 执行时占用，完成后释放 | 持续占用少量资源 |
| 灵活性 | 可指定平台、并行执行 | 按配置自动执行 |

## 错误处理

### 任务失败

如果某个任务失败，会显示错误信息但继续执行其他任务：

```
[5/14] Running: weibo
  ✗ Failed in 2.3s: Weibo API requires authentication (HTTP 432)

[6/14] Running: zhihu
  ✓ Completed in 1.8s
```

最终统计会显示失败数量：

```
============================================================
Total: 14 tasks
Success: 13
Failed: 1
Total time: 125.3s
============================================================
```

### 查看详细错误

查看日志文件获取详细错误信息：

```bash
tail -f logs/app.log | grep ERROR
```

## 性能优化建议

### 1. 使用并行执行

对于多个任务，并行执行可以显著提升速度：

```bash
# 慢：120秒
./.venv/Scripts/python manage.py run_all_tasks

# 快：35秒
./.venv/Scripts/python manage.py run_all_tasks --parallel
```

### 2. 分批执行

如果服务器资源有限，可以分批执行：

```bash
# 第一批：国内平台
./.venv/Scripts/python manage.py run_all_tasks --platform ftchinese,kr36,huxiu,zaobao,zhihu,weibo,pengpai --parallel

# 第二批：国外平台
./.venv/Scripts/python manage.py run_all_tasks --platform economist,apnews,wsj,github_trending,hacker_news,washingtonpost --parallel
```

### 3. 避免高峰期

在服务器负载较低时执行：

```bash
# 凌晨执行
0 3 * * * cd /path/to/project && ./.venv/bin/python manage.py run_all_tasks --parallel
```

## 常见问题

### Q: 可以同时运行多个 run_all_tasks 吗？

A: 不建议。虽然技术上可行，但会导致：
- 数据库写入冲突
- 资源竞争
- 重复数据

建议等待前一个执行完成后再运行。

### Q: 执行时间过长怎么办？

A: 
1. 使用 `--parallel` 并行执行
2. 只执行必要的平台
3. 检查网络连接
4. 查看日志排查慢速平台

### Q: 如何在后台执行？

A: 使用 nohup 或 screen：

```bash
# 使用 nohup
nohup ./.venv/Scripts/python manage.py run_all_tasks --parallel > output.log 2>&1 &

# 使用 screen
screen -dmS fetch ./.venv/Scripts/python manage.py run_all_tasks --parallel
```

### Q: 可以设置超时吗？

A: 当前版本没有超时设置。如果需要，可以使用系统的 timeout 命令：

```bash
# 最多执行10分钟
timeout 600 ./.venv/Scripts/python manage.py run_all_tasks --parallel
```

## 总结

`run_all_tasks` 是一个强大的工具，适合：

✅ 快速测试所有接口
✅ 手动触发数据更新
✅ 初始化数据库
✅ 调试特定平台
✅ 灵活的执行策略

配合 `run_scheduler` 使用，可以实现完整的自动化数据抓取方案。
