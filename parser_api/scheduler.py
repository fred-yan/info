"""
定时任务调度器
使用 APScheduler 实现定时抓取新闻数据
"""
import logging
import os
import threading
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from django.conf import settings
import time

logger = logging.getLogger(__name__)

# 唯一标识当前 worker 进程，用于日志区分
_WORKER_ID = f"pid-{os.getpid()}"

# 任务默认锁超时时间（秒）：正常任务 10 分钟，LLM 分析 60 分钟
_DEFAULT_LOCK_TTL = 600
_LLM_LOCK_TTL = 3600


def _try_acquire_lock(task_name: str, ttl_seconds: int = _DEFAULT_LOCK_TTL) -> bool:
    """
    尝试获取分布式任务锁（基于 MySQL）。

    原理：
      - 用 SchedulerLock 表的 task_name 作为锁键（primary key）
      - 若该锁不存在 → INSERT 成功 → 获锁
      - 若该锁存在但已过期（locked_at + ttl < now）→ UPDATE 成功 → 获锁
      - 若该锁存在且未过期 → 跳过（另一个 worker 正在执行）

    使用 select_for_update() + 事务保证原子性。
    """
    from django.db import transaction
    from django.utils import timezone
    from .models import SchedulerLock

    now = timezone.now()
    expire_before = now - timedelta(seconds=ttl_seconds)

    try:
        with transaction.atomic():
            # 尝试获取行锁
            lock_qs = SchedulerLock.objects.select_for_update(nowait=True).filter(
                task_name=task_name
            )
            existing = lock_qs.first()

            if existing is None:
                # 锁不存在，创建
                SchedulerLock.objects.create(
                    task_name=task_name,
                    locked_at=now,
                    worker_id=_WORKER_ID,
                )
                logger.info("[Lock] Acquired new lock: task=%s worker=%s", task_name, _WORKER_ID)
                return True

            if existing.locked_at <= expire_before:
                # 锁已过期，更新
                existing.locked_at = now
                existing.worker_id = _WORKER_ID
                existing.save(update_fields=["locked_at", "worker_id"])
                logger.info("[Lock] Acquired expired lock: task=%s worker=%s expired_at=%s",
                            task_name, _WORKER_ID, existing.locked_at)
                return True

            # 锁被其他 worker 持有且未过期
            logger.info("[Lock] Skipped (locked by %s at %s): task=%s worker=%s",
                        existing.worker_id, existing.locked_at.strftime("%H:%M:%S"),
                        task_name, _WORKER_ID)
            return False

    except Exception as e:
        # select_for_update(nowait=True) 在锁冲突时抛出 OperationalError，视为获锁失败
        logger.info("[Lock] Failed to acquire (concurrent conflict): task=%s err=%s", task_name, e)
        return False


def _release_lock(task_name: str) -> None:
    """任务完成后释放锁（将 locked_at 置为很久以前，使其立即过期）。"""
    from django.utils import timezone
    from datetime import timedelta
    from .models import SchedulerLock
    try:
        SchedulerLock.objects.filter(
            task_name=task_name,
            worker_id=_WORKER_ID,
        ).update(locked_at=timezone.now() - timedelta(days=1))
    except Exception as e:
        logger.warning("[Lock] Release failed: task=%s err=%s", task_name, e)

# 全局调度器实例
scheduler = None

# 追踪每批抓取任务的完成情况
_batch_lock = threading.Lock()
_batch_total = 0       # 当前批次总任务数
_batch_done = 0        # 当前批次已完成数
_batch_id = None       # 当前批次标识（触发时间）


def _on_fetch_done():
    """
    每个抓取任务完成后调用。
    当所有抓取任务都完成时，延迟 5 分钟触发 LLM 关键词分析。
    """
    global _batch_done, _batch_id, scheduler

    with _batch_lock:
        _batch_done += 1
        done = _batch_done
        total = _batch_total
        batch = _batch_id

    logger.info("[Scheduler] Fetch progress: %d/%d (batch=%s)", done, total, batch)

    if done >= total and scheduler is not None:
        run_at = datetime.now() + timedelta(minutes=5)
        job_id = "llm_after_batch_%s" % batch

        existing = scheduler.get_job(job_id)
        if existing:
            return

        scheduler.add_job(
            fetch_task_wrapper,
            trigger=DateTrigger(run_date=run_at),
            args=['keyword_analysis_llm'],
            id=job_id,
            name='LLM analysis after batch %s' % batch,
            replace_existing=True,
        )
        logger.info("[Scheduler] Scheduled LLM analysis at %s (5min after all fetches done)",
                    run_at.strftime('%H:%M:%S'))


def _reset_batch_counter():
    """在每批抓取开始时重置计数器，并设置安全超时。"""
    global _batch_done, _batch_total, _batch_id, scheduler

    scheduler_config = getattr(settings, 'SCHEDULER_CONFIG', {})
    count = 0
    for platform, config in scheduler_config.items():
        if not config.get('enabled', True):
            continue
        if 'keyword_analysis' in platform:
            continue
        count += 1

    with _batch_lock:
        _batch_done = 0
        _batch_total = count
        _batch_id = datetime.now().strftime('%H%M')

    logger.info("[Scheduler] Batch started: %d fetch tasks (batch=%s)", count, _batch_id)

    if scheduler is not None:
        fallback_time = datetime.now() + timedelta(minutes=15)
        fallback_id = "llm_fallback_%s" % _batch_id
        try:
            scheduler.add_job(
                _fallback_trigger_llm,
                trigger=DateTrigger(run_date=fallback_time),
                id=fallback_id,
                name='LLM fallback trigger (batch=%s)' % _batch_id,
                replace_existing=True,
            )
        except Exception as e:
            logger.error("[Scheduler] Failed to add fallback job: %s", e)


def _fallback_trigger_llm():
    """安全超时触发：如果 15 分钟后 LLM 分析还没被正常触发，强制执行。"""
    global scheduler, _batch_done, _batch_total

    with _batch_lock:
        done = _batch_done
        total = _batch_total

    if done < total:
        logger.warning(
            "[Scheduler] Fallback trigger: only %d/%d tasks completed, forcing LLM analysis anyway",
            done, total
        )

    if scheduler is not None:
        jobs = scheduler.get_jobs()
        for job in jobs:
            if job.id.startswith("llm_after_batch_") and job.next_run_time:
                logger.info("[Scheduler] LLM already scheduled, skipping fallback")
                return

    fetch_task_wrapper('keyword_analysis_llm')


def fetch_task_wrapper(platform: str, **kwargs):
    """
    任务包装器：调用对应平台的抓取函数

    Args:
        platform: 平台名称
        **kwargs: 额外参数（如 since 等）
    """
    logger.info("[Scheduler] Starting task: %s worker=%s", platform, _WORKER_ID)
    start_time = time.time()

    # LLM 分析任务用更长的锁超时
    ttl = _LLM_LOCK_TTL if "keyword_analysis" in platform else _DEFAULT_LOCK_TTL
    lock_key = f"task_{platform}"

    if not _try_acquire_lock(lock_key, ttl):
        logger.info("[Scheduler] Task skipped (lock held by another worker): %s", platform)
        # 注意：跳过的任务也要更新 batch 计数，否则 LLM 分析永远等不到 done==total
        if "keyword_analysis" not in platform:
            _on_fetch_done()
        return

    try:
        from parser_api import views
        from django.test import RequestFactory

        factory = RequestFactory()

        view_map = {
            'economist': views.economist_view,
            'apnews': views.apnews_view,
            'ftchinese': views.ftchinese_view,
            'wsj': views.wsj_view,
            'kr36': views.kr36_view,
            'huxiu': views.huxiu_view,
            'wscn': views.wscn_view,
            'cls': views.cls_view,
            'jiqizhixin': views.jiqizhixin_view,
            'tmtpost': views.tmtpost_view,
            'theverge': views.theverge_view,
            'techcrunch': views.techcrunch_view,
            'mittr': views.mittr_view,
            'zaobao': views.zaobao_view,
            'zaobao_hotlist': views.zaobao_hotlist_view,
            'github_trending': views.github_trending_view,
            'github_trending_daily': views.github_trending_view,
            'github_trending_weekly': views.github_trending_view,
            'github_trending_monthly': views.github_trending_view,
            'hacker_news': views.hacker_news_top_stories_view,
            'zhihu': views.zhihu_view,
            'weibo': views.weibo_view,
            'pengpai': views.pengpai_view,
            'washingtonpost': views.wst_post_view,
            'keyword_analysis': None,
            'keyword_analysis_llm': None,
        }

        if platform == 'keyword_analysis':
            from parser_api.keyword_extractor import extract_keywords
            extract_keywords()
            elapsed = time.time() - start_time
            logger.info("[Scheduler] Task completed: keyword_analysis (elapsed=%.1fs)", elapsed)
            return

        if platform == 'keyword_analysis_llm':
            from django.db import close_old_connections
            close_old_connections()
            from parser_api.llm_extractor_v2 import extract_keywords_llm_v2
            extract_keywords_llm_v2(group="domestic")
            close_old_connections()
            extract_keywords_llm_v2(group="international")
            elapsed = time.time() - start_time
            logger.info("[Scheduler] Task completed: keyword_analysis_llm (elapsed=%.1fs)", elapsed)
            return

        view_func = view_map.get(platform)
        if not view_func:
            logger.error("[Scheduler] Unknown platform: %s", platform)
            return

        if kwargs:
            request = factory.get('/', kwargs)
        else:
            request = factory.get('/')

        response = view_func(request)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            logger.info("[Scheduler] Task completed: %s (elapsed=%.1fs)", platform, elapsed)
        else:
            logger.warning("[Scheduler] Task failed: %s status=%d (elapsed=%.1fs)",
                           platform, response.status_code, elapsed)

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("[Scheduler] Task error: %s error=%s (elapsed=%.1fs)",
                     platform, e, elapsed, exc_info=True)
    finally:
        _release_lock(lock_key)
        if 'keyword_analysis' not in platform:
            _on_fetch_done()


def setup_scheduler():
    """
    设置并启动调度器
    从 settings.SCHEDULER_CONFIG 读取配置并注册任务
    """
    global scheduler

    if not getattr(settings, 'SCHEDULER_ENABLED', False):
        logger.info("[Scheduler] Scheduler is disabled in settings")
        return None

    if scheduler is not None:
        logger.warning("[Scheduler] Scheduler already running")
        return scheduler

    scheduler = BackgroundScheduler(
        timezone=getattr(settings, 'SCHEDULER_TIMEZONE', 'Asia/Shanghai')
    )

    scheduler_config = getattr(settings, 'SCHEDULER_CONFIG', {})

    if not scheduler_config:
        logger.warning("[Scheduler] No tasks configured in SCHEDULER_CONFIG")
        return None

    registered_count = 0

    for platform, config in scheduler_config.items():
        if not config.get('enabled', True):
            logger.info("[Scheduler] Task disabled: %s", platform)
            continue

        cron_expr = config.get('cron')
        if not cron_expr:
            logger.warning("[Scheduler] No cron expression for: %s", platform)
            continue

        parts = cron_expr.split()
        if len(parts) != 5:
            logger.error("[Scheduler] Invalid cron expression for %s: %s", platform, cron_expr)
            continue

        minute, hour, day, month, day_of_week = parts
        params = config.get('params', {})

        try:
            scheduler.add_job(
                fetch_task_wrapper,
                trigger=CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week,
                    timezone=getattr(settings, 'SCHEDULER_TIMEZONE', 'Asia/Shanghai')
                ),
                args=[platform],
                kwargs=params,
                id='fetch_%s' % platform,
                name='Fetch %s' % platform,
                replace_existing=True,
                max_instances=1,
            )
            registered_count += 1
            logger.info("[Scheduler] Task registered: %s cron=%s", platform, cron_expr)
        except Exception as e:
            logger.error("[Scheduler] Failed to register task %s: %s", platform, e, exc_info=True)

    if registered_count == 0:
        logger.warning("[Scheduler] No tasks registered")
        return None

    try:
        scheduler.add_job(
            _reset_batch_counter,
            trigger=CronTrigger(
                minute='0',
                hour='6,12,18,0',
                timezone=getattr(settings, 'SCHEDULER_TIMEZONE', 'Asia/Shanghai')
            ),
            id='batch_reset',
            name='Reset batch counter',
            replace_existing=True,
            max_instances=1,
        )
        logger.info("[Scheduler] Batch reset job registered")
    except Exception as e:
        logger.error("[Scheduler] Failed to register batch reset: %s", e, exc_info=True)

    scheduler.start()
    logger.info("[Scheduler] Scheduler started successfully with %d tasks", registered_count)

    return scheduler


def shutdown_scheduler():
    """关闭调度器"""
    global scheduler
    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("[Scheduler] Scheduler shutdown")


def get_scheduler_status():
    """获取调度器状态"""
    global scheduler

    if scheduler is None:
        return {"status": "disabled", "jobs": []}

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return {
        "status": "running",
        "timezone": str(scheduler.timezone),
        "jobs": jobs,
    }
