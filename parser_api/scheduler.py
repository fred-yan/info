"""
定时任务调度器 v2 - 数据库任务队列版

架构：
  Layer 1 - APScheduler CronTrigger：每天早上6点触发 _start_batch()，向数据库写入任务记录
  Layer 2 - SchedulerTask 表：持久化任务状态，select_for_update(skip_locked) 防多 worker 重复
  Layer 3 - _poll_loop()：每10秒轮询，从数据库抢 pending 任务，提交线程池执行

可观测性设计（每个阶段都有日志，不静默失败）：
  - APScheduler 生命周期：job 注册/触发/错误/misfire/shutdown 全部记录
  - poll 线程：每次循环心跳（DEBUG），线程存活状态，异常记录
  - 线程池：任务提交/完成/失败 全部记录
  - 批次生命周期：创建/开始/完成/超时 全部记录
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
from apscheduler.events import (
    EVENT_SCHEDULER_STARTED,
    EVENT_SCHEDULER_SHUTDOWN,
    EVENT_SCHEDULER_PAUSED,
    EVENT_SCHEDULER_RESUMED,
    EVENT_JOB_ADDED,
    EVENT_JOB_REMOVED,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_ERROR,
    EVENT_JOB_MISSED,
    EVENT_JOB_SUBMITTED,
    EVENT_JOB_MAX_INSTANCES,
)
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ─────────────────────────── 常量 ───────────────────────────

_WORKER_ID = f"pid-{os.getpid()}"

_MAX_RETRY = {
    'fetch':       2,
    'llm_extract': 1,
    'llm_cluster': 1,
}

_TASK_TIMEOUT = {
    'fetch':       180,
    'llm_extract': 600,
    'llm_cluster': 1800,
}

_PLATFORM_FETCH_TIMEOUT = {
    'hacker_news':             600,
    'zaobao':                  360,
    'zaobao_hotlist':          360,
    'github_trending_daily':   360,
    'github_trending_weekly':  360,
    'github_trending_monthly': 360,
}

_TASK_TO_DB_PLATFORM = {
    'zaobao_hotlist':          'zaobao',
    'github_trending_daily':   'github',
    'github_trending_weekly':  'github',
    'github_trending_monthly': 'github',
    'hacker_news':             'hackernews',
}

_DB_PLATFORM_TO_FETCH_TASKS: dict[str, list[str]] = {}
for _t, _p in _TASK_TO_DB_PLATFORM.items():
    _DB_PLATFORM_TO_FETCH_TASKS.setdefault(_p, []).append(_t)

_POLL_INTERVAL = 10
_ZOMBIE_CHECK_INTERVAL = 300
_BATCH_HARD_TIMEOUT_MINUTES = 120

# poll 循环心跳日志间隔（秒），避免每10秒都打 DEBUG 日志刷屏
_POLL_HEARTBEAT_INTERVAL = 300  # 每5分钟打一次心跳

# ─────────────────────────── 全局状态 ───────────────────────────

scheduler: BackgroundScheduler | None = None
_thread_pool: ThreadPoolExecutor | None = None
_poll_stop_event = threading.Event()
_poll_thread: threading.Thread | None = None


# ═══════════════════════════════════════════════════════════════
# APScheduler 事件监听
# ═══════════════════════════════════════════════════════════════

def _setup_apscheduler_listeners(sched: BackgroundScheduler) -> None:
    """
    注册 APScheduler 全量事件监听。
    覆盖 scheduler 生命周期 + job 执行生命周期，任何异常都有日志输出。
    """

    # ── Scheduler 生命周期 ──
    def on_scheduler_started(event):
        logger.info("[APScheduler] Scheduler STARTED worker=%s", _WORKER_ID)

    def on_scheduler_shutdown(event):
        # 这是最关键的：scheduler 意外停止时必须有日志
        logger.error("[APScheduler] Scheduler SHUTDOWN! worker=%s "
                     "这意味着 CronTrigger 不再触发，定时任务将停止。"
                     "请检查是否有未处理异常导致 scheduler 线程退出。",
                     _WORKER_ID)

    def on_scheduler_paused(event):
        logger.warning("[APScheduler] Scheduler PAUSED worker=%s", _WORKER_ID)

    def on_scheduler_resumed(event):
        logger.info("[APScheduler] Scheduler RESUMED worker=%s", _WORKER_ID)

    # ── Job 生命周期 ──
    def on_job_added(event):
        logger.info("[APScheduler] Job ADDED: job_id=%s", event.job_id)

    def on_job_removed(event):
        logger.warning("[APScheduler] Job REMOVED: job_id=%s "
                       "job被移除后将不再触发，请确认是否预期行为。", event.job_id)

    def on_job_submitted(event):
        # job 被提交到执行线程（即将触发）
        logger.info("[APScheduler] Job SUBMITTED: job_id=%s scheduled_at=%s worker=%s",
                    event.job_id, event.scheduled_run_time, _WORKER_ID)

    def on_job_executed(event):
        logger.info("[APScheduler] Job EXECUTED: job_id=%s scheduled_at=%s retval=%s worker=%s",
                    event.job_id, event.scheduled_run_time, event.retval, _WORKER_ID)

    def on_job_error(event):
        # job 执行时抛出异常 —— 最关键：默认不重试，下次 cron 才会再触发
        logger.error("[APScheduler] Job ERROR: job_id=%s scheduled_at=%s exception=%s worker=%s",
                     event.job_id, event.scheduled_run_time, event.exception, _WORKER_ID,
                     exc_info=event.traceback)

    def on_job_missed(event):
        # job 因为超过 misfire_grace_time 而被跳过
        # 多 worker 场景下 max_instances=1 会导致其他 worker 的触发被 misfire
        logger.warning("[APScheduler] Job MISSED (misfire): job_id=%s scheduled_at=%s worker=%s "
                       "如果频繁出现此日志，说明多个 worker 在竞争同一个 job 触发，属正常现象。",
                       event.job_id, event.scheduled_run_time, _WORKER_ID)

    def on_job_max_instances(event):
        # job 达到 max_instances 上限，本次触发被丢弃
        logger.warning("[APScheduler] Job MAX_INSTANCES reached: job_id=%s "
                       "本次触发被丢弃，已有实例正在运行。worker=%s",
                       event.job_id, _WORKER_ID)

    sched.add_listener(on_scheduler_started,  EVENT_SCHEDULER_STARTED)
    sched.add_listener(on_scheduler_shutdown,  EVENT_SCHEDULER_SHUTDOWN)
    sched.add_listener(on_scheduler_paused,    EVENT_SCHEDULER_PAUSED)
    sched.add_listener(on_scheduler_resumed,   EVENT_SCHEDULER_RESUMED)
    sched.add_listener(on_job_added,           EVENT_JOB_ADDED)
    sched.add_listener(on_job_removed,         EVENT_JOB_REMOVED)
    sched.add_listener(on_job_submitted,       EVENT_JOB_SUBMITTED)
    sched.add_listener(on_job_executed,        EVENT_JOB_EXECUTED)
    sched.add_listener(on_job_error,           EVENT_JOB_ERROR)
    sched.add_listener(on_job_missed,          EVENT_JOB_MISSED)
    sched.add_listener(on_job_max_instances,   EVENT_JOB_MAX_INSTANCES)

    logger.info("[APScheduler] Event listeners registered (11 events) worker=%s", _WORKER_ID)


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
    logger.info("[Scheduler] _start_batch called: batch_id=%s worker=%s", batch_id, _WORKER_ID)

    scheduler_config = getattr(settings, 'SCHEDULER_CONFIG', {})
    platforms = [
        p for p, cfg in scheduler_config.items()
        if cfg.get('enabled', True) and 'keyword_analysis' not in p
    ]

    if not platforms:
        logger.warning("[Scheduler] No enabled platforms in SCHEDULER_CONFIG (total_keys=%d)",
                       len(scheduler_config))
        return

    if SchedulerTask.objects.filter(batch_id=batch_id).exists():
        logger.info("[Scheduler] Batch %s already exists, skipping (worker=%s)",
                    batch_id, _WORKER_ID)
        return

    logger.info("[Scheduler] Starting batch %s with %d platforms", batch_id, len(platforms))

    tasks_to_create = []
    for platform in platforms:
        tasks_to_create.append(SchedulerTask(
            batch_id=batch_id,
            task_type=SchedulerTask.TYPE_FETCH,
            platform=platform,
            status=SchedulerTask.STATUS_PENDING,
        ))
        tasks_to_create.append(SchedulerTask(
            batch_id=batch_id,
            task_type=SchedulerTask.TYPE_LLM_EXTRACT,
            platform=platform,
            status=SchedulerTask.STATUS_WAITING,
        ))

    tasks_to_create.append(SchedulerTask(
        batch_id=batch_id,
        task_type=SchedulerTask.TYPE_LLM_CLUSTER,
        platform=SchedulerTask.PLATFORM_ALL,
        status=SchedulerTask.STATUS_WAITING,
    ))

    SchedulerTask.objects.bulk_create(tasks_to_create, ignore_conflicts=True)
    logger.info("[Scheduler] Batch %s: created %d tasks (%d fetch + %d llm_extract + 1 llm_cluster)",
                batch_id, len(tasks_to_create), len(platforms), len(platforms))

    # 注册硬超时兜底
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
    else:
        logger.warning("[Scheduler] scheduler is None when trying to register hard timeout "
                       "for batch %s — hard timeout will NOT run!", batch_id)


def _batch_hard_timeout(batch_id: str):
    from .models import SchedulerTask

    logger.warning("[Scheduler] Hard timeout triggered for batch %s", batch_id)

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
    from django.db import transaction
    from .models import SchedulerTask

    concurrency = getattr(settings, 'SCHEDULER_CONCURRENCY', {
        'fetch': 3, 'llm_extract': 2, 'llm_cluster': 1, 'total': 5,
    })

    for task_type in [SchedulerTask.TYPE_FETCH,
                      SchedulerTask.TYPE_LLM_EXTRACT,
                      SchedulerTask.TYPE_LLM_CLUSTER]:
        max_concurrent = concurrency.get(task_type, 1)
        running_count = SchedulerTask.objects.filter(
            status=SchedulerTask.STATUS_RUNNING,
            task_type=task_type,
        ).count()
        if running_count >= max_concurrent:
            continue

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

        task.status = SchedulerTask.STATUS_DONE
        task.finished_at = timezone.now()
        task.error_msg = ''
        task.save(update_fields=['status', 'finished_at', 'error_msg'])
        logger.info("[Scheduler] Task done: [%s] %s/%s elapsed=%.1fs",
                    task.batch_id, task.task_type, task.platform,
                    (task.finished_at - task.started_at).total_seconds())

        _on_task_done(task)

    except Exception as e:
        elapsed = (timezone.now() - task.started_at).total_seconds() if task.started_at else 0
        logger.error("[Scheduler] Task error: [%s] %s/%s elapsed=%.1fs error=%s",
                     task.batch_id, task.task_type, task.platform, elapsed, e, exc_info=True)
        _handle_task_failure(task, str(e))


def _handle_task_failure(task, error_msg: str):
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
        _on_task_failed(task)


def _on_task_done(task):
    from .models import SchedulerTask

    if task.task_type == SchedulerTask.TYPE_FETCH:
        _maybe_unlock_llm_extract(task.batch_id, task.platform)
    elif task.task_type == SchedulerTask.TYPE_LLM_EXTRACT:
        _check_and_unlock_cluster(task.batch_id)


def _on_task_failed(task):
    from .models import SchedulerTask

    if task.task_type == SchedulerTask.TYPE_FETCH:
        _maybe_unlock_llm_extract(task.batch_id, task.platform)
    elif task.task_type == SchedulerTask.TYPE_LLM_EXTRACT:
        _check_and_unlock_cluster(task.batch_id)


def _maybe_unlock_llm_extract(batch_id: str, completed_platform: str):
    from .models import SchedulerTask

    db_platform = _TASK_TO_DB_PLATFORM.get(completed_platform, completed_platform)
    sibling_task_names = _DB_PLATFORM_TO_FETCH_TASKS.get(db_platform)
    if sibling_task_names:
        all_fetch_platforms = list(set(sibling_task_names) | {completed_platform})
        for t, p in _TASK_TO_DB_PLATFORM.items():
            if p == db_platform:
                all_fetch_platforms.append(t)
        all_fetch_platforms = list(set(all_fetch_platforms))
    else:
        all_fetch_platforms = [completed_platform]

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

    any_succeeded = SchedulerTask.objects.filter(
        batch_id=batch_id,
        task_type=SchedulerTask.TYPE_FETCH,
        platform__in=all_fetch_platforms,
        status=SchedulerTask.STATUS_DONE,
    ).exists()

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
        _check_and_unlock_cluster(batch_id)


def _check_and_unlock_cluster(batch_id: str):
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
    from parser_api import views
    from django.test import RequestFactory
    from django.conf import settings

    platform = task.platform
    scheduler_config = getattr(settings, 'SCHEDULER_CONFIG', {})
    params = scheduler_config.get(platform, {}).get('params', {})

    view_map = {
        'economist':               views.economist_view,
        'apnews':                  views.apnews_view,
        'ftchinese':               views.ftchinese_view,
        'wsj':                     views.wsj_view,
        'kr36':                    views.kr36_view,
        'huxiu':                   views.huxiu_view,
        'wscn':                    views.wscn_view,
        'cls':                     views.cls_view,
        'jiqizhixin':              views.jiqizhixin_view,
        'tmtpost':                 views.tmtpost_view,
        'theverge':                views.theverge_view,
        'techcrunch':              views.techcrunch_view,
        'mittr':                   views.mittr_view,
        'zaobao':                  views.zaobao_view,
        'zaobao_hotlist':          views.zaobao_hotlist_view,
        'github_trending_daily':   views.github_trending_view,
        'github_trending_weekly':  views.github_trending_view,
        'github_trending_monthly': views.github_trending_view,
        'hacker_news':             views.hacker_news_top_stories_view,
        'zhihu':                   views.zhihu_view,
        'weibo':                   views.weibo_view,
        'pengpai':                 views.pengpai_view,
        'washingtonpost':          views.wst_post_view,
    }

    view_func = view_map.get(platform)
    if not view_func:
        raise ValueError(f"No view mapped for platform: {platform}")

    factory = RequestFactory()
    request = (factory.get('/', {**params, '_batch_id': task.batch_id})
               if params else factory.get('/', {'_batch_id': task.batch_id}))
    response = view_func(request)

    if response.status_code != 200:
        raise RuntimeError(f"Fetch failed: platform={platform} status={response.status_code}")


def _run_llm_extract(task):
    from django.db import close_old_connections
    from parser_api.llm_platform_extractor import extract_phrases_for_platform

    db_platform = _TASK_TO_DB_PLATFORM.get(task.platform, task.platform)
    close_old_connections()
    result = extract_phrases_for_platform(db_platform, force=False,
                                          batch_start=task.batch_id)

    if result.get('error') and not result.get('skipped_by_cache'):
        raise RuntimeError(f"LLM extract error: {result['error']}")

    logger.info("[Scheduler] llm_extract done: task=%s db_platform=%s articles=%d elapsed=%.1fs cached=%s",
                task.platform, db_platform,
                result.get('article_count', 0),
                result.get('elapsed_seconds', 0),
                result.get('skipped_by_cache', False))
    close_old_connections()


def _run_llm_cluster(task):
    import gc
    from django.db import close_old_connections
    from parser_api.llm_extractor_v2 import extract_keywords_llm_v2

    lock_key = 'task_llm_cluster_global'
    if not _try_acquire_global_lock(lock_key, ttl_seconds=_TASK_TIMEOUT['llm_cluster']):
        logger.debug("[Scheduler] llm_cluster skipped (global lock held) batch=%s", task.batch_id)
        return

    try:
        logger.info("[Scheduler] llm_cluster starting domestic group batch=%s", task.batch_id)
        close_old_connections()
        extract_keywords_llm_v2(group="domestic")
        close_old_connections()
        gc.collect()
        logger.info("[Scheduler] llm_cluster starting international group batch=%s", task.batch_id)
        extract_keywords_llm_v2(group="international")
        close_old_connections()
        gc.collect()
        logger.info("[Scheduler] llm_cluster completed both groups batch=%s", task.batch_id)
    finally:
        _release_global_lock(lock_key)


# ═══════════════════════════════════════════════════════════════
# 异常恢复：僵死检测 & 孤儿任务认领
# ═══════════════════════════════════════════════════════════════

def _reclaim_orphaned_tasks():
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
    后台线程：每 _POLL_INTERVAL 秒轮询一次数据库。
    每 _POLL_HEARTBEAT_INTERVAL 秒打一次心跳日志，证明线程还活着。
    任何异常都记录日志，不静默退出。
    """
    logger.info("[Scheduler] Poll loop started (worker=%s)", _WORKER_ID)
    last_zombie_check = time.monotonic()
    last_heartbeat = time.monotonic()
    poll_count = 0

    while not _poll_stop_event.is_set():
        try:
            poll_count += 1
            now_mono = time.monotonic()

            # 心跳日志（每5分钟）
            if now_mono - last_heartbeat >= _POLL_HEARTBEAT_INTERVAL:
                # 顺带检查 APScheduler 是否还活着
                sched_alive = (scheduler is not None and scheduler.running)
                logger.info("[Scheduler] Poll heartbeat: worker=%s poll_count=%d "
                            "apscheduler_running=%s",
                            _WORKER_ID, poll_count, sched_alive)
                if not sched_alive:
                    logger.error("[Scheduler] APScheduler is NOT running! "
                                 "CronTrigger 已停止，定时任务将不会被触发。worker=%s", _WORKER_ID)
                last_heartbeat = now_mono

            # 僵死检测（每5分钟）
            if now_mono - last_zombie_check >= _ZOMBIE_CHECK_INTERVAL:
                _detect_zombie_tasks()
                last_zombie_check = now_mono

            # 检查线程池容量并领取任务
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
            logger.error("[Scheduler] Poll loop error (will continue): %s", e, exc_info=True)

        _poll_stop_event.wait(timeout=_POLL_INTERVAL)

    logger.info("[Scheduler] Poll loop stopped (worker=%s poll_count=%d)", _WORKER_ID, poll_count)


# ═══════════════════════════════════════════════════════════════
# SchedulerLock 全局互斥锁
# ═══════════════════════════════════════════════════════════════

def _try_acquire_global_lock(task_name: str, ttl_seconds: int) -> bool:
    from django.db import transaction
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
    from .models import SchedulerLock
    try:
        SchedulerLock.objects.filter(
            task_name=task_name,
            worker_id=_WORKER_ID,
        ).update(locked_at=timezone.now() - timedelta(days=1))
    except Exception as e:
        logger.warning("[Scheduler] Release global lock failed: task=%s err=%s", task_name, e)


# ═══════════════════════════════════════════════════════════════
# 公开接口：setup / shutdown / status
# ═══════════════════════════════════════════════════════════════

def setup_scheduler():
    global scheduler, _thread_pool, _poll_thread, _poll_stop_event

    if not getattr(settings, 'SCHEDULER_ENABLED', False):
        logger.info("[Scheduler] Scheduler disabled in settings")
        return None

    if scheduler is not None:
        logger.warning("[Scheduler] Scheduler already running")
        return scheduler

    logger.info("[Scheduler] Setting up scheduler worker=%s", _WORKER_ID)

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

    # APScheduler
    tz = getattr(settings, 'SCHEDULER_TIMEZONE', 'Asia/Shanghai')
    scheduler = BackgroundScheduler(timezone=tz)

    # 注册所有 APScheduler 事件监听（关键：全覆盖不遗漏）
    _setup_apscheduler_listeners(scheduler)

    # 注册 CronTrigger
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
        logger.warning("[Scheduler] No cron expressions found in SCHEDULER_CONFIG, using default")
        cron_exprs = {'0 6 * * *'}

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
                timezone=tz,
            ),
            id=f'start_batch_{cron_expr.replace(" ", "_")}',
            name=f'Start batch [{cron_expr}]',
            replace_existing=True,
            max_instances=1,
            # misfire_grace_time=None：无论延迟多久都执行，不因 misfire 跳过
            misfire_grace_time=None,
            # coalesce=True：多次积压只触发一次
            coalesce=True,
        )
        logger.info("[Scheduler] Batch trigger registered: cron=%s timezone=%s", cron_expr, tz)

    scheduler.start()
    logger.info("[Scheduler] APScheduler started, jobs=%d", len(scheduler.get_jobs()))

    # 打印所有已注册的 job 和下次执行时间
    for job in scheduler.get_jobs():
        logger.info("[Scheduler] Registered job: id=%s name=%s next_run=%s",
                    job.id, job.name,
                    job.next_run_time.isoformat() if job.next_run_time else "None")

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
    global scheduler, _thread_pool, _poll_thread

    logger.info("[Scheduler] Shutting down worker=%s", _WORKER_ID)
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

    logger.info("[Scheduler] Shutdown complete worker=%s", _WORKER_ID)


def get_scheduler_status():
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

    poll_alive = (_poll_thread is not None and _poll_thread.is_alive())
    apscheduler_running = (scheduler is not None and scheduler.running)

    return {
        "status": "running",
        "worker_id": _WORKER_ID,
        "timezone": str(scheduler.timezone),
        "apscheduler_running": apscheduler_running,
        "poll_thread_alive": poll_alive,
        "jobs": jobs,
        "recent_tasks": recent_tasks,
    }
