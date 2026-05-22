"""
定时任务调度器
使用 APScheduler 实现定时抓取新闻数据
"""
import logging
import threading
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from django.conf import settings
import time

logger = logging.getLogger(__name__)

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

    logger.info(f"[Scheduler] Fetch progress: {done}/{total} (batch={batch})")

    if done >= total and scheduler is not None:
        # 所有抓取任务完成，5 分钟后触发 LLM 分析
        run_at = datetime.now() + timedelta(minutes=5)
        job_id = f"llm_after_batch_{batch}"

        # 避免重复添加
        existing = scheduler.get_job(job_id)
        if existing:
            return

        scheduler.add_job(
            fetch_task_wrapper,
            trigger=DateTrigger(run_date=run_at),
            args=['keyword_analysis_llm'],
            id=job_id,
            name=f'LLM analysis after batch {batch}',
            replace_existing=True,
        )
        logger.info(f"[Scheduler] Scheduled LLM analysis at {run_at.strftime('%H:%M:%S')} (5min after all fetches done)")


def _reset_batch_counter():
    """在每批抓取开始时重置计数器，并设置安全超时。"""
    global _batch_done, _batch_total, _batch_id, scheduler

    # 计算当前批次有多少个启用的抓取任务（排除 keyword_analysis 类）
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

    logger.info(f"[Scheduler] Batch started: {count} fetch tasks (batch={_batch_id})")

    # 安全超时：15 分钟后无论如何都触发 LLM 分析（防止某些任务卡住导致永远不触发）
    if scheduler is not None:
        fallback_time = datetime.now() + timedelta(minutes=15)
        fallback_id = f"llm_fallback_{_batch_id}"
        try:
            scheduler.add_job(
                _fallback_trigger_llm,
                trigger=DateTrigger(run_date=fallback_time),
                id=fallback_id,
                name=f'LLM fallback trigger (batch={_batch_id})',
                replace_existing=True,
            )
        except Exception as e:
            logger.error(f"[Scheduler] Failed to add fallback job: {e}")


def _fallback_trigger_llm():
    """安全超时触发：如果 15 分钟后 LLM 分析还没被正常触发，强制执行。"""
    global scheduler, _batch_done, _batch_total

    with _batch_lock:
        done = _batch_done
        total = _batch_total

    if done < total:
        logger.warning(
            f"[Scheduler] Fallback trigger: only {done}/{total} tasks completed, "
            f"forcing LLM analysis anyway"
        )

    # 检查是否已经有正常触发的 LLM 任务在排队
    if scheduler is not None:
        jobs = scheduler.get_jobs()
        for job in jobs:
            if job.id.startswith("llm_after_batch_") and job.next_run_time:
                logger.info("[Scheduler] LLM already scheduled, skipping fallback")
                return

    # 直接执行
    fetch_task_wrapper('keyword_analysis_llm')


def fetch_task_wrapper(platform: str, **kwargs):
    """
    任务包装器：调用对应平台的抓取函数
    
    Args:
        platform: 平台名称
        **kwargs: 额外参数（如 since 等）
    """
    logger.info(f"[Scheduler] Starting task: {platform}")
    start_time = time.time()
    
    try:
        # 动态导入对应的 view 函数
        from parser_api import views
        from django.test import RequestFactory
        
        # 创建模拟请求
        factory = RequestFactory()
        
        # 根据平台调用对应的 view
        view_map = {
            'economist': views.economist_view,
            'apnews': views.apnews_view,
            'ftchinese': views.ftchinese_view,
            'wsj': views.wsj_view,
            'kr36': views.kr36_view,
            'huxiu': views.huxiu_view,
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
            'keyword_analysis': None,  # 特殊处理
            'keyword_analysis_llm': None,  # 特殊处理
        }
        
        # keyword_analysis 走独立逻辑（已弃用，保留兼容）
        if platform == 'keyword_analysis':
            from parser_api.keyword_extractor import extract_keywords
            extract_keywords()
            elapsed = time.time() - start_time
            logger.info(f"[Scheduler] Task completed: keyword_analysis (elapsed={elapsed:.1f}s)")
            return

        # keyword_analysis_llm 走 LLM 逻辑（国内 + 国际两组都跑）
        if platform == 'keyword_analysis_llm':
            from parser_api.llm_keyword_extractor import extract_keywords_llm
            extract_keywords_llm(group="domestic")
            extract_keywords_llm(group="international")
            elapsed = time.time() - start_time
            logger.info(f"[Scheduler] Task completed: keyword_analysis_llm (elapsed={elapsed:.1f}s)")
            return

        view_func = view_map.get(platform)
        if not view_func:
            logger.error(f"[Scheduler] Unknown platform: {platform}")
            return
        
        # 构建请求（带参数）
        if kwargs:
            request = factory.get('/', kwargs)
        else:
            request = factory.get('/')
        
        # 执行任务
        response = view_func(request)
        
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            logger.info(f"[Scheduler] Task completed: {platform} (elapsed={elapsed:.1f}s)")
        else:
            logger.warning(f"[Scheduler] Task failed: {platform} status={response.status_code} (elapsed={elapsed:.1f}s)")
            
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"[Scheduler] Task error: {platform} error={e} (elapsed={elapsed:.1f}s)", exc_info=True)
    finally:
        # 抓取任务（非 keyword_analysis 类）完成后更新计数
        if 'keyword_analysis' not in platform:
            _on_fetch_done()


def setup_scheduler():
    """
    设置并启动调度器
    从 settings.SCHEDULER_CONFIG 读取配置并注册任务
    
    Returns:
        BackgroundScheduler 实例或 None
    """
    global scheduler
    
    if not getattr(settings, 'SCHEDULER_ENABLED', False):
        logger.info("[Scheduler] Scheduler is disabled in settings")
        return None
    
    if scheduler is not None:
        logger.warning("[Scheduler] Scheduler already running")
        return scheduler
    
    # 创建调度器
    scheduler = BackgroundScheduler(
        timezone=getattr(settings, 'SCHEDULER_TIMEZONE', 'Asia/Shanghai')
    )
    
    # 从配置中加载任务
    scheduler_config = getattr(settings, 'SCHEDULER_CONFIG', {})
    
    if not scheduler_config:
        logger.warning("[Scheduler] No tasks configured in SCHEDULER_CONFIG")
        return None
    
    registered_count = 0
    
    for platform, config in scheduler_config.items():
        if not config.get('enabled', True):
            logger.info(f"[Scheduler] Task disabled: {platform}")
            continue
        
        cron_expr = config.get('cron')
        if not cron_expr:
            logger.warning(f"[Scheduler] No cron expression for: {platform}")
            continue
        
        # 解析 cron 表达式
        parts = cron_expr.split()
        if len(parts) != 5:
            logger.error(f"[Scheduler] Invalid cron expression for {platform}: {cron_expr}")
            continue
        
        minute, hour, day, month, day_of_week = parts
        
        # 获取额外参数
        params = config.get('params', {})
        
        # 添加任务
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
                id=f'fetch_{platform}',
                name=f'Fetch {platform}',
                replace_existing=True,
                max_instances=1,  # 防止任务重叠
            )
            registered_count += 1
            logger.info(f"[Scheduler] Task registered: {platform} cron={cron_expr}")
        except Exception as e:
            logger.error(f"[Scheduler] Failed to register task {platform}: {e}", exc_info=True)
    
    if registered_count == 0:
        logger.warning("[Scheduler] No tasks registered")
        return None
    
    # 注册批次重置任务：在每批抓取开始时重置计数器
    # 使用与抓取任务相同的 cron 时间（0 6,12,18,0），但提前 1 秒执行
    # 实际上 APScheduler 按注册顺序触发同时间任务，所以直接用同一时间即可
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
        logger.error(f"[Scheduler] Failed to register batch reset: {e}", exc_info=True)

    # 启动调度器
    scheduler.start()
    logger.info(f"[Scheduler] Scheduler started successfully with {registered_count} tasks")
    
    return scheduler


def shutdown_scheduler():
    """
    关闭调度器
    """
    global scheduler
    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("[Scheduler] Scheduler shutdown")


def get_scheduler_status():
    """
    获取调度器状态
    
    Returns:
        dict: 包含调度器状态和任务列表
    """
    global scheduler
    
    if scheduler is None:
        return {
            "status": "disabled",
            "jobs": []
        }
    
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
        "jobs": jobs
    }
