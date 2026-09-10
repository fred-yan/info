# 定时任务调度器重构设计文档

## 背景

原调度器基于 APScheduler + 进程内内存状态，存在以下问题：

1. **状态丢失**：`_batch_done/_batch_total` 等计数全在进程内存，Gunicorn 重启或 worker crash 后丢失，依赖 15 分钟内存 fallback 兜底（同样会丢失）
2. **LLM 触发时机晚**：所有平台都抓完才触发 LLM 分析，某个平台卡住会导致整批延迟
3. **防重复有盲区**：`SchedulerLock` 基于 TTL 过期，worker 被 kill 后锁残留最长 600s，且不支持失败重试
4. **并发不可控**：只有 fetcher 层 `Semaphore(3)` 兜底，LLM 提取任务无限制并发
5. **可观测性差**：任务状态只有日志，无法查询历史

---

## 新方案：数据库任务队列

### 核心原则

> 把"状态"从内存移到数据库，APScheduler 只负责按时触发批次启动，不负责执行。

---

## 架构

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: APScheduler CronTrigger                       │
│  每6小时触发 _start_batch()                             │
│  向 SchedulerTask 表写入一批 pending/waiting 任务记录   │
│  不直接执行任务                                         │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│  Layer 2: SchedulerTask 数据库任务表                    │
│                                                         │
│  task_type = "fetch" | "llm_extract" | "llm_cluster"   │
│  status    = "pending"|"waiting"|"running"|             │
│              "done"|"failed"|"skipped"                  │
│                                                         │
│  select_for_update(skip_locked) 保证多worker不重复       │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│  Layer 3: _poll_and_execute() 每10秒轮询                │
│  从 pending 任务里抢任务（行锁），提交到线程池执行       │
│  线程池大小 = SCHEDULER_CONCURRENCY['total']            │
│  各类型并发上限由 SCHEDULER_CONCURRENCY 分别控制        │
└─────────────────────────────────────────────────────────┘
```

---

## 任务表结构

```python
class SchedulerTask(models.Model):
    batch_id     = CharField(max_length=20)     # "20260909_1800"
    task_type    = CharField(max_length=20)     # fetch / llm_extract / llm_cluster
    platform     = CharField(max_length=64)     # 平台名，llm_cluster 时为 "__all__"
    status       = CharField(max_length=16)     # pending/waiting/running/done/failed/skipped
    worker_id    = CharField(max_length=64)     # 执行该任务的 worker 进程 ID
    created_at   = DateTimeField(auto_now_add)
    started_at   = DateTimeField(null)
    finished_at  = DateTimeField(null)
    error_msg    = TextField(null)
    retry_count  = IntegerField(default=0)
    timeout_at   = DateTimeField(null)          # 僵死检测用：预计超时时间

    unique_together: (batch_id, task_type, platform)
    indexes: (status, task_type), (batch_id, status)
```

---

## 任务流水线

```
_start_batch() 写入：
  fetch(economist)       → pending
  fetch(ftchinese)       → pending
  fetch(kr36)            → pending
  ...（所有启用的平台）
  llm_extract(economist) → waiting   ← 等对应 fetch 完成才变 pending
  llm_extract(ftchinese) → waiting
  llm_extract(kr36)      → waiting
  ...
  llm_cluster(__all__)   → waiting   ← 等所有 llm_extract 完成才变 pending

执行过程（_poll_and_execute 每10秒轮询）：
  并发抓取（≤3个） → 每个平台抓完立即触发 llm_extract → 全部完成触发 llm_cluster
```

---

## 状态流转

```
          waiting
             │ 依赖完成
             ▼
          pending ◄──────────────────────────────┐
             │ worker 抢到                        │ retry_count < MAX
             ▼                                   │
          running ──────────── 异常/超时 ─────────┤
             │                                   │ retry_count >= MAX
          成功                                    ▼
             ▼                                 failed
           done
             │ fetch done
             ▼
     对应 llm_extract → pending
             │ 所有 llm_extract done/failed/skipped
             ▼
     llm_cluster → pending
```

---

## 防重复机制（多 worker）

```python
with transaction.atomic():
    task = (
        SchedulerTask.objects
        .select_for_update(skip_locked=True)
        .filter(status='pending', task_type__in=allowed_types)
        .order_by('created_at')
        .first()
    )
    if task:
        task.status = 'running'
        task.worker_id = WORKER_ID
        task.started_at = now()
        task.timeout_at = now() + TASK_TIMEOUT[task.task_type]
        task.save()
```

`skip_locked=True`：已被其他 worker 行锁锁住的行直接跳过，不阻塞。多个 worker 同时 poll 时各自拿到不同任务，天然防重复。

---

## 异常情况处理

### 情况1：任务执行抛异常

```
retry_count += 1
if retry_count < MAX_RETRY[task_type]:
    status → pending   （重新入队，下一次 poll 会重试）
else:
    status → failed
    fetch failed → 对应 llm_extract → skipped
```

重试上限：
- `fetch`：2次（Playwright 偶发失败较多）
- `llm_extract`：1次（LLM 成本高）
- `llm_cluster`：1次

### 情况2：Worker 被 kill（OOM/SIGKILL）

finally 不执行，任务卡在 running。

**僵死检测**（每5分钟扫描一次）：
```
timeout_at < now() AND status = 'running'
→ retry_count < MAX → 重置为 pending
→ retry_count >= MAX → 标记 failed
```

timeout_at 按任务类型设置：
- `fetch`：180s
- `llm_extract`：600s
- `llm_cluster`：1800s

### 情况3：服务重启，running 任务变孤儿

`setup_scheduler()` 启动时执行 `_reclaim_orphaned_tasks()`：

```
所有 status='running' 的任务 → 重置为 pending
（本进程刚启动，不可能是它在跑这些任务）
```

### 情况4：整批任务超时（fetch 永远不完成）

batch 创建时注册 **硬超时兜底**（APScheduler DateTrigger，batch 开始后 120 分钟）：

```
_batch_hard_timeout(batch_id):
    llm_cluster 若仍是 waiting/pending → 强制改为 pending
    未完成的 llm_extract → 标记 skipped
```

### 情况5：两批次重叠（上批 llm_cluster 还在跑，下批 fetch 已开始）

batch_id 不同（"20260909_0600" vs "20260909_1200"），互不干扰。
llm_cluster 用全局 SchedulerLock 保证同一时间只有一个在执行。

---

## 并发度配置

```python
# settings.py
SCHEDULER_CONCURRENCY = {
    'fetch': 3,        # 同时最多3个平台抓取（Playwright 内存限制）
    'llm_extract': 2,  # 同时最多2个平台做LLM短语提取
    'llm_cluster': 1,  # 归类永远串行
    'total': 5,        # 线程池总大小
}
```

poll 时先检查各类型当前 running 数量，未达上限才抢对应类型的任务。

---

## 与现有代码的对接

| 文件 | 变更 |
|---|---|
| `parser_api/models.py` | 新增 `SchedulerTask` 模型 |
| `parser_api/scheduler.py` | 完全重写 |
| `django_api/settings.py` | 新增 `SCHEDULER_CONCURRENCY` |
| `parser_api/llm_platform_extractor.py` | 不改 |
| `parser_api/llm_extractor_v2.py` | 不改 |
| `parser_api/views.py` | 不改 |

对外接口保持不变：`setup_scheduler()` / `shutdown_scheduler()` / `get_scheduler_status()`

---

## 方案对比

| 维度 | 旧方案 | 新方案 |
|---|---|---|
| 状态存储 | 进程内存 | 数据库 |
| 重启后恢复 | 依赖15min内存fallback | 启动时 reclaim + 僵死检测 |
| 防重复 | SchedulerLock TTL过期 | select_for_update(skip_locked) |
| 失败重试 | 不重试 | 按类型配置重试次数 |
| Worker crash恢复 | TTL 600s后 | timeout_at到期自动重置 |
| LLM触发时机 | 所有平台完成后 | 每个平台完成后立即触发 |
| 并发控制 | fetcher层Semaphore(3) | 按任务类型分别限制 |
| 可观测性 | 只有日志 | 数据库完整状态记录 |
| 批次重叠 | 共享内存计数会混淆 | batch_id隔离互不影响 |
| 硬超时兜底 | 15min DateTrigger（内存） | 120min数据库任务 |
