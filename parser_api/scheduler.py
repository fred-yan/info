"""
定时任务调度器 v2 - 数据库任务队列版

架构：
  Layer 1 - APScheduler CronTrigger：每6小时触发 _start_batch()，向数据库写入任务记录
  Layer 2 - SchedulerTask 表：持久化任务状态，select_for_update(skip_locked) 防多 worker 重复
  Layer 3 - _poll_and_execute()：每10秒轮询，从数据库抢 pending 任务，提交线程池执行

流水线：
  fetch(平台A) → 成功 → llm_extract(平台A)
  fetch(平台B) → 成功 → llm_extract(平台B)
  ...
  所有 llm_extract done/failed/skipped → llm_cluster(__all__)

异常恢复：
  - 任务失败：retry_count < MAX_RETRY 则重置为 pending 重试，否则 failed
  - Worker crash（finally 未执行）：僵死检测扫描 timeout_at < now 的 running 任务并重置
  - 服务重启：startup 时将所有 running 任务重置为 pending（_reclaim_orphaned_tasks）
  - 硬超时兜底：批次开始 120 分钟后强制推进 llm_cluster，防止 fetch 永远不完成
"""

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ─────────────────────────── 常量 ───────────────────────────

_WORKER_ID = f"pid-{os.getpid()}"

# 各任务类型最大重试次数
_MAX_RETRY = {
    'fetch':       2,
    'llm_extract': 1,
    'llm_cluster': 1,
}

# 各任务类型默认超时时间（秒），用于僵死检测
_TASK_TIMEOUT = {
    'fetch':       180,   # Playwright 最长 3 分钟（默认）
    'llm_extract': 600,   # 单平台 LLM 最长 10 分钟
    'llm_cluster': 1800,  # 全局归类最长 30 分钟
}

# 特定平台的 fetch 超时覆盖（秒）
# hacker_news：并发拉取 200 条 item 详情（5线程×10s超时），实测需 2-4 分钟
# zaobao/zaobao_hotlist：Playwright + 多页抓取，实测需 3-5 分钟
_PLATFORM_FETCH_TIMEOUT = {
    'hacker_news':          600,   # 10 分钟
    'zaobao':               360,   # 6 分钟
    'zaobao_hotlist':       360,   # 6 分钟
    'github_trending_daily':   360,
    'github_trending_weekly':  360,
    'github_trending_monthly': 360,
}

# 调度器任务名 → 数据库 Info.platform 字段值的映射
# 部分任务名与写入数据库时的 platform 字段不一致，llm_extract 需用实际字段值查库
_TASK_TO_DB_PLATFORM = {
    'zaobao_hotlist':          'zaobao',      # hotlist 也写入 platform="zaobao"
    'github_trending_daily':   'github',
    'github_trending_weekly':  'github',
    'github_trending_monthly': 'github',
    'hacker_news':             'hackernews',  # 数据库里无下划线
}

# 反向映射：db_platform → 所有对应的调度任务名列表
# 用于"同一 db_platform 的所有 fetch 全部完成才解锁 llm_extract"
_DB_PLATFORM_TO_FETCH_TASKS: dict[str, list[str]] = {}
for _t, _p in _TASK_TO_DB_PLATFORM.items():
    _DB_PLATFORM_TO_FETCH_TASKS.setdefault(_p, []).append(_t)

# 任务轮询间隔（秒）
_POLL_INTERVAL = 10

# 僵死检测间隔（秒）
_ZOMBIE_CHECK_INTERVAL = 300

# 批次硬超时（分钟），超时后强制推进 llm_cluster
_BATCH_HARD_TIMEOUT_MINUTES = 120

# ─────────────────────────── 全局状态 ───────────────────────────

scheduler: BackgroundScheduler | None = None
_thread_pool: ThreadPoolExecutor | None = None
_poll_stop_event = threading.Event()
_poll_thread: threading.Thread | None = None


# ═══════════════════════════════════════════════════════════════
# 批次启动
# ═══════════════════════════════════════════════════════════════

def _start_batch():
    """
    CronTrigger 触发入口。
    向 SchedulerTask 表写入本批次所有任务记录，然后由 poll 循环逐步执行。
    若当前批次已存在（重复触发），跳过。
    """
    from .models import SchedulerTask

    batch_id = datetime.now().strftime('%Y%m%d_%H%M')
    scheduler_config = getattr(settings, 'SCHEDULER_CONFIG', {})

    # 收集启用的抓取平台
    platforms = [
        p for p, cfg in scheduler_config.items()
        if cfg.get('enabled', True) and 'keyword_analysis' not in p
    ]

    if not platforms:
        logger.warning("[Scheduler] No enabled platforms in SCHEDULER_CONFIG (total_keys=%d)", len(scheduler_config))
        return

    # 防重复：同一批次已存在则跳过
    if SchedulerTask.objects.filter(batch_id=batch_id).exists():
        logger.info("[Scheduler] Batch %s already exists, skipping", batch_id)
        return

    logger.info("[Scheduler] Starting batch %s with %d platforms", batch_id, len(platforms))

    tasks_to_create = []
    for platform in platforms:
        # fetch 任务：直接 pending
        tasks_to_create.append(SchedulerTask(
            batch_id=batch_id,
            task_type=SchedulerTask.TYPE_FETCH,
            platform=platform,
            status=SchedulerTask.STATUS_PENDING,
        ))
        # llm_extract 任务：等待对应 fetch 完成
        tasks_to_create.append(SchedulerTask(
            batch_id=batch_id,
            task_type=SchedulerTask.TYPE_LLM_EXTRACT,
            platform=platform,
            status=SchedulerTask.STATUS_WAITING,
        ))

    # llm_cluster：等待所有 llm_extract 完成
    tasks_to_create.append(SchedulerTask(
        batch_id=batch_id,
        task_type=SchedulerTask.TYPE_LLM_CLUSTER,
        platform=SchedulerTask.PLATFORM_ALL,
        status=SchedulerTask.STATUS_WAITING,
    ))

    SchedulerTask.objects.bulk_create(tasks_to_create, ignore_conflicts=True)
    logger.info("[Scheduler] Batch %s: created %d tasks (%d fetch + %d llm_extract + 1 llm_cluster)",
                batch_id, len(tasks_to_create), len(platforms), len(platforms))

    # 注册硬超时兜底：120 分钟后强制推进 llm_cluster
    if scheduler is not None:
        hard_timeout_at = datetime.now() + timedelta(minutes=_BATCH_HARD_TIMEOUT_MINUTES)
        try:
            scheduler.add_job(
                _batch_hard_timeout,
                trigger=DateTrigger(run_date=hard_timeout_at),
                args=[batch_id],
                id=f'hard_timeout_{batch_id}',
                name=f'Hard timeout for batch {batch_id}',
                replace_existing=True,
            )
            logger.info("[Scheduler] Batch %s: hard timeout scheduled at %s",
                        batch_id, hard_timeout_at.strftime('%H:%M'))
        except Exception as e:
            logger.error("[Scheduler] Failed to schedule hard timeout for batch %s: %s", batch_id, e)


def _batch_hard_timeout(batch_id: str):
    """
    硬超时兜底：批次开始 120 分钟后触发。
    将未完成的 llm_extract 标记为 skipped，强制将 llm_cluster 改为 pending。
    """
    from .models import SchedulerTask

    logger.warning("[Scheduler] Hard timeout triggered for batch %s", batch_id)

    # 将仍在 waiting/pending/running 的 llm_extract 标记为 skipped
    skipped = SchedulerTask.objects.filter(
        batch_id=batch_id,
        task_type=SchedulerTask.TYPE_LLM_EXTRACT,
        status__in=[SchedulerTask.STATUS_WAITING, SchedulerTask.STATUS_PENDING],
    ).update(
        status=SchedulerTask.STATUS_SKIPPED,
        error_msg='hard timeout: forced skip after batch timeout',
        finished_at=timezone.now(),
    )
    if skipped:
        logger.warning("[Scheduler] Hard timeout: skipped %d llm_extract tasks for batch %s",
                       skipped, batch_id)

    # 强制推进 llm_cluster
    cluster = SchedulerTask.objects.filter(
        batch_id=batch_id,
        task_type=SchedulerTask.TYPE_LLM_CLUSTER,
        status__in=[SchedulerTask.STATUS_WAITING, SchedulerTask.STATUS_PENDING],
    ).first()
    if cluster:
        cluster.status = SchedulerTask.STATUS_PENDING
        cluster.error_msg = 'hard timeout: forced to pending'
        cluster.save(update_fields=['status', 'error_msg'])
        logger.warning("[Scheduler] Hard timeout: forced llm_cluster to pending for batch %s", batch_id)
    else:
        logger.info("[Scheduler] Hard timeout: llm_cluster already done/running for batch %s", batch_id)


# ═══════════════════════════════════════════════════════════════
# 任务抢占与执行
# ═══════════════════════════════════════════════════════════════

def _pick_next_task():
    """
    从数据库抢一个 pending 任务。
    使用 select_for_update(skip_locked=True) 保证多 worker 不重复领取同一任务。
    按并发度限制：先检查各类型当前 running 数量，未达上限才抢对应类型任务。

    返回 SchedulerTask 实例（已改为 running），或 None（无可用任务）。
    """
    from django.db import transaction
    from .models import SchedulerTask

    concurrency = getattr(settings, 'SCHEDULER_CONCURRENCY', {
        'fetch': 3, 'llm_extract': 2, 'llm_cluster': 1, 'total': 5,
    })

    # 按优先级依次尝试：fetch > llm_extract > llm_cluster
    for task_type in [SchedulerTask.TYPE_FETCH,
                      SchedulerTask.TYPE_LLM_EXTRACT,
                      SchedulerTask.TYPE_LLM_CLUSTER]:
        max_concurrent = concurrency.get(task_type, 1)
        running_count = SchedulerTask.objects.filter(
            status=SchedulerTask.STATUS_RUNNING,
            task_type=task_type,
        ).count()
        if running_count >= max_concurrent:
            continue  # 该类型已达并发上限

        try:
            with transaction.atomic():
                task = (
                    SchedulerTask.objects
                    .select_for_update(skip_locked=True)
                    .filter(
                        status=SchedulerTask.STATUS_PENDING,
                        task_type=task_type,
                    )
                    .order_by('created_at')
                    .first()
                )
                if task is None:
                    continue

                now = timezone.now()
                task.status = SchedulerTask.STATUS_RUNNING
                task.worker_id = _WORKER_ID
                task.started_at = now
                # 平台级超时优先于类型级默认值
                if task_type == SchedulerTask.TYPE_FETCH:
                    timeout_secs = _PLATFORM_FETCH_TIMEOUT.get(task.platform, _TASK_TIMEOUT['fetch'])
                else:
                    timeout_secs = _TASK_TIMEOUT[task_type]
                task.timeout_at = now + timedelta(seconds=timeout_secs)
                task.save(update_fields=['status', 'worker_id', 'started_at', 'timeout_at'])
                return task
        except Exception as e:
            logger.debug("[Scheduler] pick_next_task lock conflict for type=%s: %s", task_type, e)
            continue

    return None


def _execute_task(task):
    """
    执行单个任务。成功/失败后更新状态，并触发下游任务。
    """
    from .models import SchedulerTask

    logger.info("[Scheduler] Executing task: [%s] %s/%s (retry=%d worker=%s)",
                task.batch_id, task.task_type, task.platform, task.retry_count, _WORKER_ID)

    try:
        if task.task_type == SchedulerTask.TYPE_FETCH:
            _run_fetch(task)
        elif task.task_type == SchedulerTask.TYPE_LLM_EXTRACT:
            _run_llm_extract(task)
        elif task.task_type == SchedulerTask.TYPE_LLM_CLUSTER:
            _run_llm_cluster(task)
        else:
            raise ValueError(f"Unknown task_type: {task.task_type}")

        # 成功
        task.status = SchedulerTask.STATUS_DONE
        task.finished_at = timezone.now()
        task.error_msg = ''
        task.save(update_fields=['status', 'finished_at', 'error_msg'])
        logger.info("[Scheduler] Task done: [%s] %s/%s elapsed=%.1fs",
                    task.batch_id, task.task_type, task.platform,
                    (task.finished_at - task.started_at).total_seconds())

        # 触发下游
        _on_task_done(task)

    except Exception as e:
        elapsed = (timezone.now() - task.started_at).total_seconds() if task.started_at else 0
        logger.error("[Scheduler] Task error: [%s] %s/%s elapsed=%.1fs error=%s",
                     task.batch_id, task.task_type, task.platform, elapsed, e, exc_info=True)
        _handle_task_failure(task, str(e))


def _handle_task_failure(task, error_msg: str):
    """
    任务失败处理：
    - retry_count < MAX_RETRY → 重置为 pending，等待下次 poll 重试
    - retry_count >= MAX_RETRY → 标记 failed，触发下游跳过逻辑
    """
    from .models import SchedulerTask

    task.retry_count += 1
    task.error_msg = error_msg
    task.finished_at = timezone.now()
    max_retry = _MAX_RETRY.get(task.task_type, 1)

    if task.retry_count <= max_retry:
        task.status = SchedulerTask.STATUS_PENDING
        task.worker_id = ''
        task.started_at = None
        task.timeout_at = None
        task.save(update_fields=['status', 'retry_count', 'error_msg',
                                  'finished_at', 'worker_id', 'started_at', 'timeout_at'])
        logger.warning("[Scheduler] Task will retry (%d/%d): [%s] %s/%s",
                       task.retry_count, max_retry,
                       task.batch_id, task.task_type, task.platform)
    else:
        task.status = SchedulerTask.STATUS_FAILED
        task.save(update_fields=['status', 'retry_count', 'error_msg', 'finished_at'])
        logger.error("[Scheduler] Task permanently failed: [%s] %s/%s",
                     task.batch_id, task.task_type, task.platform)
        # 触发下游跳过逻辑
        _on_task_failed(task)


def _on_task_done(task):
    """任务成功完成后，触发下游任务。"""
    from .models import SchedulerTask

    if task.task_type == SchedulerTask.TYPE_FETCH:
        # 检查同一 db_platform 的所有 fetch 是否全部结束（done/failed/skipped）
        # 全部结束才解锁 llm_extract，确保所有相关数据都已写入 DB
        _maybe_unlock_llm_extract(task.batch_id, task.platform)

    elif task.task_type == SchedulerTask.TYPE_LLM_EXTRACT:
        # llm_extract 完成 → 检查是否所有 llm_extract 都结束
        _check_and_unlock_cluster(task.batch_id)


def _on_task_failed(task):
    """任务永久失败后，跳过下游任务并尝试推进流水线。"""
    from .models import SchedulerTask

    if task.task_type == SchedulerTask.TYPE_FETCH:
        # 同一 db_platform 的所有 fetch 都结束（含本次失败）才处理 llm_extract
        _maybe_unlock_llm_extract(task.batch_id, task.platform)

    elif task.task_type == SchedulerTask.TYPE_LLM_EXTRACT:
        # llm_extract 永久失败 → 检查是否可以推进 llm_cluster
        _check_and_unlock_cluster(task.batch_id)


def _maybe_unlock_llm_extract(batch_id: str, completed_platform: str):
    """
    某个 fetch 任务完成或失败后调用。
    检查同一 db_platform 的所有 fetch 任务是否全部结束：
      - 若全部结束且至少一个成功(done) → 解锁对应 llm_extract（→ pending）
      - 若全部结束但全部失败/跳过     → 将 llm_extract 标记为 skipped
      - 若还有未完成的                 → 等待，不做任何操作
    """
    from .models import SchedulerTask

    db_platform = _TASK_TO_DB_PLATFORM.get(completed_platform, completed_platform)

    # 找出同一 db_platform 下所有的调度任务名
    sibling_task_names = _DB_PLATFORM_TO_FETCH_TASKS.get(db_platform)
    if sibling_task_names:
        # 有多个 fetch 任务对应同一 db_platform（如 zaobao/zaobao_hotlist）
        all_fetch_platforms = sibling_task_names + [
            t for t in [db_platform] if t not in sibling_task_names
        ]
        # 还需包含 db_platform 本身（它可能也是一个任务名，如 zaobao）
        all_fetch_platforms = list(set(sibling_task_names) | {completed_platform})
        # 再加上所有映射到该 db_platform 的任务名
        for t, p in _TASK_TO_DB_PLATFORM.items():
            if p == db_platform:
                all_fetch_platforms.append(t)
        all_fetch_platforms = list(set(all_fetch_platforms))
    else:
        all_fetch_platforms = [completed_platform]

    # 检查这些 fetch 任务是否还有未结束的
    still_running = SchedulerTask.objects.filter(
        batch_id=batch_id,
        task_type=SchedulerTask.TYPE_FETCH,
        platform__in=all_fetch_platforms,
        status__in=[SchedulerTask.STATUS_PENDING,
                    SchedulerTask.STATUS_WAITING,
                    SchedulerTask.STATUS_RUNNING],
    ).exists()

    if still_running:
        logger.info("[Scheduler] Waiting for sibling fetch tasks before llm_extract: "
                    "db_platform=%s batch=%s", db_platform, batch_id)
        return

    # 所有相关 fetch 都结束了，检查是否有成功的
    any_succeeded = SchedulerTask.objects.filter(
        batch_id=batch_id,
        task_type=SchedulerTask.TYPE_FETCH,
        platform__in=all_fetch_platforms,
        status=SchedulerTask.STATUS_DONE,
    ).exists()

    # llm_extract 的 platform 字段用的是各自的调度任务名，需逐一处理
    for fetch_platform in all_fetch_platforms:
        if any_succeeded:
            updated = SchedulerTask.objects.filter(
                batch_id=batch_id,
                task_type=SchedulerTask.TYPE_LLM_EXTRACT,
                platform=fetch_platform,
                status=SchedulerTask.STATUS_WAITING,
            ).update(status=SchedulerTask.STATUS_PENDING)
            if updated:
                logger.info("[Scheduler] Unlocked llm_extract: platform=%s db_platform=%s batch=%s",
                            fetch_platform, db_platform, batch_id)
        else:
            # 所有相关 fetch 都失败，跳过 llm_extract
            SchedulerTask.objects.filter(
                batch_id=batch_id,
                task_type=SchedulerTask.TYPE_LLM_EXTRACT,
                platform=fetch_platform,
                status=SchedulerTask.STATUS_WAITING,
            ).update(
                status=SchedulerTask.STATUS_SKIPPED,
                error_msg=f'skipped: all fetch tasks failed for db_platform={db_platform}',
                finished_at=timezone.now(),
            )
            logger.warning("[Scheduler] Skipped llm_extract: platform=%s "
                           "db_platform=%s (all fetch failed) batch=%s",
                           fetch_platform, db_platform, batch_id)

    if not any_succeeded:
        # 全部跳过后检查是否可以推进 llm_cluster
        _check_and_unlock_cluster(batch_id)


def _check_and_unlock_cluster(batch_id: str):
    """
    检查当前批次所有 llm_extract 是否全部结束（done/failed/skipped）。
    若是，将 llm_cluster 从 waiting 改为 pending。
    """
    from .models import SchedulerTask

    total = SchedulerTask.objects.filter(
        batch_id=batch_id,
        task_type=SchedulerTask.TYPE_LLM_EXTRACT,
    ).count()

    finished = SchedulerTask.objects.filter(
        batch_id=batch_id,
        task_type=SchedulerTask.TYPE_LLM_EXTRACT,
        status__in=[SchedulerTask.STATUS_DONE,
                    SchedulerTask.STATUS_FAILED,
                    SchedulerTask.STATUS_SKIPPED],
    ).count()

    logger.info("[Scheduler] llm_extract progress: %d/%d finished (batch=%s)",
                finished, total, batch_id)

    if finished >= total and total > 0:
        updated = SchedulerTask.objects.filter(
            batch_id=batch_id,
            task_type=SchedulerTask.TYPE_LLM_CLUSTER,
            status=SchedulerTask.STATUS_WAITING,
        ).update(status=SchedulerTask.STATUS_PENDING)
        if updated:
            logger.info("[Scheduler] All llm_extract done → unlocked llm_cluster (batch=%s)", batch_id)


# ═══════════════════════════════════════════════════════════════
# 各任务类型的具体执行逻辑
# ═══════════════════════════════════════════════════════════════

def _run_fetch(task):
    """执行平台抓取任务。"""
    from parser_api import views
    from django.test import RequestFactory
    from django.conf import settings

    platform = task.platform
    scheduler_config = getattr(settings, 'SCHEDULER_CONFIG', {})
    params = scheduler_config.get(platform, {}).get('params', {})

    view_map = {
        'economist':             views.economist_view,
        'apnews':                views.apnews_view,
        'ftchinese':             views.ftchinese_view,
        'wsj':                   views.wsj_view,
        'kr36':                  views.kr36_view,
        'huxiu':                 views.huxiu_view,
        'wscn':                  views.wscn_view,
        'cls':                   views.cls_view,
        'jiqizhixin':            views.jiqizhixin_view,
        'tmtpost':               views.tmtpost_view,
        'theverge':              views.theverge_view,
        'techcrunch':            views.techcrunch_view,
        'mittr':                 views.mittr_view,
        'zaobao':                views.zaobao_view,
        'zaobao_hotlist':        views.zaobao_hotlist_view,
        'github_trending_daily':   views.github_trending_view,
        'github_trending_weekly':  views.github_trending_view,
        'github_trending_monthly': views.github_trending_view,
        'hacker_news':           views.hacker_news_top_stories_view,
        'zhihu':                 views.zhihu_view,
        'weibo':                 views.weibo_view,
        'pengpai':               views.pengpai_view,
        'washingtonpost':        views.wst_post_view,
    }

    view_func = view_map.get(platform)
    if not view_func:
        raise ValueError(f"No view mapped for platform: {platform}")

    factory = RequestFactory()
    request = factory.get('/', params) if params else factory.get('/')
    response = view_func(request)

    if response.status_code != 200:
        raise RuntimeError(f"Fetch failed: platform={platform} status={response.status_code}")


def _run_llm_extract(task):
    """执行单平台 LLM 短语提取任务。"""
    from django.db import close_old_connections
    from parser_api.llm_platform_extractor import extract_phrases_for_platform

    # 调度器任务名可能与数据库 platform 字段不一致，需转换
    db_platform = _TASK_TO_DB_PLATFORM.get(task.platform, task.platform)

    close_old_connections()
    result = extract_phrases_for_platform(db_platform, force=False)

    if result.get('error') and not result.get('skipped_by_cache'):
        raise RuntimeError(f"LLM extract error: {result['error']}")

    logger.info("[Scheduler] llm_extract done: task=%s db_platform=%s articles=%d elapsed=%.1fs cached=%s",
                task.platform, db_platform,
                result.get('article_count', 0),
                result.get('elapsed_seconds', 0),
                result.get('skipped_by_cache', False))
    close_old_connections()


def _run_llm_cluster(task):
    """执行全局 LLM 短语归类任务（Stage2）。"""
    from django.db import close_old_connections
    from parser_api.llm_extractor_v2 import extract_keywords_llm_v2

    # 使用 SchedulerLock 保证同一时间只有一个 llm_cluster 在运行（跨批次防重复）
    from parser_api.scheduler_lock import try_acquire_lock, release_lock
    lock_key = 'task_llm_cluster_global'
    if not try_acquire_lock(lock_key, ttl_seconds=_TASK_TIMEOUT['llm_cluster']):
        logger.debug("[Scheduler] llm_cluster skipped (global lock held) batch=%s", task.batch_id)
        return

    try:
        close_old_connections()
        extract_keywords_llm_v2(group="domestic")
        close_old_connections()
        extract_keywords_llm_v2(group="international")
    finally:
        release_lock(lock_key)


# ═══════════════════════════════════════════════════════════════
# 异常恢复：僵死检测 & 孤儿任务认领
# ═══════════════════════════════════════════════════════════════

def _reclaim_orphaned_tasks():
    """
    服务启动时调用。
    将所有 running 状态的任务重置为 pending——本进程刚启动，
    不可能是它在处理这些任务，必定是上一个进程 crash 留下的孤儿。
    """
    from .models import SchedulerTask

    count = SchedulerTask.objects.filter(
        status=SchedulerTask.STATUS_RUNNING,
    ).update(
        status=SchedulerTask.STATUS_PENDING,
        worker_id='',
        started_at=None,
        timeout_at=None,
    )
    if count:
        logger.warning("[Scheduler] Reclaimed %d orphaned running tasks on startup", count)
    else:
        logger.info("[Scheduler] No orphaned tasks found on startup")


def _detect_zombie_tasks():
    """
    僵死任务检测（每5分钟运行一次）。
    timeout_at < now 且 status=running 的任务，视为僵死（worker 被 kill）。
    根据 retry_count 决定重试还是标记 failed。
    """
    from .models import SchedulerTask

    now = timezone.now()
    zombies = list(SchedulerTask.objects.filter(
        status=SchedulerTask.STATUS_RUNNING,
        timeout_at__lt=now,
    ))

    if not zombies:
        return

    logger.warning("[Scheduler] Found %d zombie tasks", len(zombies))
    for task in zombies:
        logger.warning("[Scheduler] Zombie: [%s] %s/%s worker=%s timeout_at=%s started_at=%s",
                       task.batch_id, task.task_type, task.platform,
                       task.worker_id, task.timeout_at, task.started_at)
        max_retry = _MAX_RETRY.get(task.task_type, 1)
        task.retry_count += 1
        task.error_msg = f'zombie: killed after timeout (worker={task.worker_id})'
        task.finished_at = now

        if task.retry_count <= max_retry:
            task.status = SchedulerTask.STATUS_PENDING
            task.worker_id = ''
            task.started_at = None
            task.timeout_at = None
            task.save(update_fields=['status', 'retry_count', 'error_msg',
                                      'finished_at', 'worker_id', 'started_at', 'timeout_at'])
            logger.warning("[Scheduler] Zombie reset to pending (%d/%d retries): [%s] %s/%s",
                           task.retry_count, max_retry,
                           task.batch_id, task.task_type, task.platform)
        else:
            task.status = SchedulerTask.STATUS_FAILED
            task.save(update_fields=['status', 'retry_count', 'error_msg', 'finished_at'])
            logger.error("[Scheduler] Zombie permanently failed: [%s] %s/%s",
                         task.batch_id, task.task_type, task.platform)
            _on_task_failed(task)


# ═══════════════════════════════════════════════════════════════
# Poll 循环
# ═══════════════════════════════════════════════════════════════

def _poll_loop():
    """
    后台线程：每 _POLL_INTERVAL 秒轮询一次数据库，
    抢 pending 任务提交到线程池执行，同时定期执行僵死检测。
    """
    logger.info("[Scheduler] Poll loop started (worker=%s)", _WORKER_ID)
    last_zombie_check = time.monotonic()

    while not _poll_stop_event.is_set():
        try:
            # 僵死检测（每 _ZOMBIE_CHECK_INTERVAL 秒）
            if time.monotonic() - last_zombie_check >= _ZOMBIE_CHECK_INTERVAL:
                _detect_zombie_tasks()
                last_zombie_check = time.monotonic()

            # 检查线程池是否还有空间
            concurrency = getattr(settings, 'SCHEDULER_CONCURRENCY',
                                  {'fetch': 3, 'llm_extract': 2, 'llm_cluster': 1, 'total': 5})
            total_limit = concurrency.get('total', 5)

            from .models import SchedulerTask
            total_running = SchedulerTask.objects.filter(
                status=SchedulerTask.STATUS_RUNNING,
            ).count()

            if total_running < total_limit:
                task = _pick_next_task()
                if task is not None:
                    _thread_pool.submit(_execute_task, task)
                    logger.debug("[Scheduler] Submitted task to pool: [%s] %s/%s",
                                 task.batch_id, task.task_type, task.platform)

        except Exception as e:
            logger.error("[Scheduler] Poll loop error: %s", e, exc_info=True)

        _poll_stop_event.wait(timeout=_POLL_INTERVAL)

    logger.info("[Scheduler] Poll loop stopped")


# ═══════════════════════════════════════════════════════════════
# SchedulerLock 兼容层（供 llm_cluster 全局锁使用）
# ═══════════════════════════════════════════════════════════════

def _try_acquire_global_lock(task_name: str, ttl_seconds: int) -> bool:
    """复用 SchedulerLock 表实现全局互斥锁（主要用于 llm_cluster）。"""
    from django.db import transaction
    from datetime import timedelta
    from .models import SchedulerLock

    now = timezone.now()
    expire_before = now - timedelta(seconds=ttl_seconds)

    try:
        with transaction.atomic():
            lock_qs = SchedulerLock.objects.select_for_update(nowait=True).filter(
                task_name=task_name
            )
            existing = lock_qs.first()

            if existing is None:
                SchedulerLock.objects.create(
                    task_name=task_name,
                    locked_at=now,
                    worker_id=_WORKER_ID,
                )
                return True

            if existing.locked_at <= expire_before:
                existing.locked_at = now
                existing.worker_id = _WORKER_ID
                existing.save(update_fields=["locked_at", "worker_id"])
                return True

            return False
    except Exception:
        return False


def _release_global_lock(task_name: str):
    """释放全局互斥锁。"""
    from datetime import timedelta
    from .models import SchedulerLock
    try:
        SchedulerLock.objects.filter(
            task_name=task_name,
            worker_id=_WORKER_ID,
        ).update(locked_at=timezone.now() - timedelta(days=1))
    except Exception as e:
        logger.warning("[Scheduler] Release global lock failed: task=%s err=%s", task_name, e)


# 在 _run_llm_cluster 里直接用模块级函数，避免循环导入
def _run_llm_cluster(task):  # noqa: F811 — 覆盖上面的占位定义
    """执行全局 LLM 短语归类任务（Stage2），带全局互斥锁。"""
    from django.db import close_old_connections
    from parser_api.llm_extractor_v2 import extract_keywords_llm_v2

    lock_key = 'task_llm_cluster_global'
    if not _try_acquire_global_lock(lock_key, ttl_seconds=_TASK_TIMEOUT['llm_cluster']):
        logger.debug("[Scheduler] llm_cluster skipped (global lock held) batch=%s", task.batch_id)
        return

    try:
        close_old_connections()
        extract_keywords_llm_v2(group="domestic")
        close_old_connections()
        extract_keywords_llm_v2(group="international")
    finally:
        _release_global_lock(lock_key)


# ═══════════════════════════════════════════════════════════════
# 公开接口：setup / shutdown / status
# ═══════════════════════════════════════════════════════════════

def setup_scheduler():
    """
    启动调度器。从 settings.SCHEDULER_CONFIG 读取 cron 配置，注册批次启动任务。
    同时启动 poll 循环线程和线程池。
    对外接口与旧版保持一致。
    """
    global scheduler, _thread_pool, _poll_thread, _poll_stop_event

    if not getattr(settings, 'SCHEDULER_ENABLED', False):
        logger.info("[Scheduler] Scheduler disabled in settings")
        return None

    if scheduler is not None:
        logger.warning("[Scheduler] Scheduler already running")
        return scheduler

    # 服务启动时认领孤儿任务
    try:
        _reclaim_orphaned_tasks()
    except Exception as e:
        logger.error("[Scheduler] Failed to reclaim orphaned tasks: %s", e)

    # 线程池
    concurrency = getattr(settings, 'SCHEDULER_CONCURRENCY',
                          {'fetch': 3, 'llm_extract': 2, 'llm_cluster': 1, 'total': 5})
    total_workers = concurrency.get('total', 5)
    _thread_pool = ThreadPoolExecutor(max_workers=total_workers, thread_name_prefix='sched-worker')
    logger.info("[Scheduler] Thread pool created: max_workers=%d", total_workers)

    # APScheduler（仅用于 CronTrigger 触发 _start_batch）
    scheduler = BackgroundScheduler(
        timezone=getattr(settings, 'SCHEDULER_TIMEZONE', 'Asia/Shanghai')
    )

    # 从 SCHEDULER_CONFIG 提取唯一的 cron 表达式，注册批次启动任务
    scheduler_config = getattr(settings, 'SCHEDULER_CONFIG', {})
    cron_exprs = set()
    for platform, cfg in scheduler_config.items():
        if not cfg.get('enabled', True):
            continue
        if 'keyword_analysis' in platform:
            continue
        cron = cfg.get('cron', '')
        if cron:
            cron_exprs.add(cron)

    if not cron_exprs:
        logger.warning("[Scheduler] No cron expressions found in SCHEDULER_CONFIG")
        cron_exprs = {'0 6,12,18,0 * * *'}  # 默认

    for cron_expr in cron_exprs:
        parts = cron_expr.split()
        if len(parts) != 5:
            logger.error("[Scheduler] Invalid cron: %s", cron_expr)
            continue
        minute, hour, day, month, day_of_week = parts
        scheduler.add_job(
            _start_batch,
            trigger=CronTrigger(
                minute=minute, hour=hour, day=day, month=month,
                day_of_week=day_of_week,
                timezone=getattr(settings, 'SCHEDULER_TIMEZONE', 'Asia/Shanghai'),
            ),
            id=f'start_batch_{cron_expr.replace(" ", "_")}',
            name=f'Start batch [{cron_expr}]',
            replace_existing=True,
            max_instances=1,
        )
        logger.info("[Scheduler] Batch trigger registered: cron=%s", cron_expr)

    scheduler.start()

    # 启动 poll 循环线程
    _poll_stop_event.clear()
    _poll_thread = threading.Thread(
        target=_poll_loop,
        name='scheduler-poll',
        daemon=True,
    )
    _poll_thread.start()

    logger.info("[Scheduler] Started successfully (worker=%s pool=%d)", _WORKER_ID, total_workers)
    return scheduler


def shutdown_scheduler():
    """关闭调度器、poll 线程、线程池。"""
    global scheduler, _thread_pool, _poll_thread

    _poll_stop_event.set()
    if _poll_thread is not None:
        _poll_thread.join(timeout=15)
        _poll_thread = None

    if _thread_pool is not None:
        _thread_pool.shutdown(wait=False)
        _thread_pool = None

    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None

    logger.info("[Scheduler] Shutdown complete")


def get_scheduler_status():
    """
    获取调度器状态。对外接口与旧版保持一致，额外返回近期任务队列状态。
    """
    global scheduler

    if scheduler is None:
        return {"status": "disabled", "jobs": [], "recent_tasks": []}

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    # 最近3个批次的任务统计
    recent_tasks = []
    try:
        from .models import SchedulerTask
        from django.db.models import Count

        recent_batches = (
            SchedulerTask.objects
            .values('batch_id')
            .distinct()
            .order_by('-batch_id')[:3]
        )
        for row in recent_batches:
            bid = row['batch_id']
            stats = (
                SchedulerTask.objects
                .filter(batch_id=bid)
                .values('task_type', 'status')
                .annotate(count=Count('id'))
            )
            recent_tasks.append({
                'batch_id': bid,
                'stats': list(stats),
            })
    except Exception as e:
        logger.debug("[Scheduler] get_scheduler_status stats error: %s", e)

    return {
        "status": "running",
        "worker_id": _WORKER_ID,
        "timezone": str(scheduler.timezone),
        "jobs": jobs,
        "recent_tasks": recent_tasks,
    }
