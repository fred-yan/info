"""
单平台 LLM 短语提取
按平台逐个处理，序号从1开始，避免全局序号混乱。
"""
import json
import logging
import math
import time as _time

from django.db.models import Max
from django.utils import timezone

from .models import Info, LLMPhraseExtraction, LLMBatchLog
from .llm_extractor_tiny import NewsPhraseExtractor, LLMConfig
from .llm_prompts import STAGE1_SYSTEM_PROMPT, STAGE1_USER_PROMPT_TEMPLATE
from .llm_extractor_v2 import _call_llm, _validate_stage1_result

logger = logging.getLogger(__name__)

# 每条标题单批 LLM 调用预估耗时（秒），用于计算预期超时时间
_SECONDS_PER_TITLE = 1.5


def estimate_timeout(article_count: int, batch_size: int) -> int:
    """
    根据文章数预估最长执行时间（秒）。
    返回建议的客户端等待时间（向上取整到10秒整数倍）。
    """
    batches = math.ceil(article_count / batch_size)
    estimated = batches * batch_size * _SECONDS_PER_TITLE
    # 向上取整到10的倍数，最少30秒
    return max(30, math.ceil(estimated / 10) * 10)


def extract_phrases_for_platform(platform: str, force: bool = False) -> dict:
    """
    对单个平台的最新一批文章做 LLM 短语提取（仅阶段1）。

    - 序号从 1 开始（平台内局部序号），避免全局序号引起的 LLM 混乱
    - 文章数 <= batch_size 时一次性发送，否则分批
    - 12小时缓存：若平台文章均已有缓存且 force=False，跳过

    返回：
    {
        "platform": "ftchinese",
        "article_count": 20,
        "batch_size": 25,
        "batches": 1,
        "estimated_timeout_seconds": 60,
        "elapsed_seconds": 18.3,
        "results": [
            {"article_id": 123, "title": "xxx", "extracted_phrases": [...], "normalized_phrases": [...]},
            ...
        ],
        "skipped_by_cache": false,
        "error": null
    }
    """
    t0 = _time.monotonic()
    now = timezone.now()
    batch_size = LLMConfig.BATCH_SIZE

    # 1. 取该平台最新一批文章
    latest = Info.objects.filter(platform=platform).aggregate(m=Max("date"))["m"]
    if not latest:
        return {
            "platform": platform, "article_count": 0, "batch_size": batch_size,
            "batches": 0, "estimated_timeout_seconds": 30, "elapsed_seconds": 0,
            "results": [], "skipped_by_cache": False, "error": "该平台无数据",
        }

    articles = list(
        Info.objects.filter(platform=platform, date=latest)
        .order_by("section", "rank", "id")
    )
    article_count = len(articles)
    batches_count = math.ceil(article_count / batch_size)
    estimated_timeout = estimate_timeout(article_count, batch_size)

    logger.info("extract_phrases_for_platform platform=%s articles=%d batches=%d timeout=%ds",
                platform, article_count, batches_count, estimated_timeout)

    # 2. 缓存检查（12小时内，不 force 时跳过）
    if not force:
        from datetime import timedelta
        cached_ids = set(
            LLMPhraseExtraction.objects.filter(
                article_id__in=[a.id for a in articles],
                analysis_time__gte=now - timedelta(hours=12),
            ).values_list("article_id", flat=True)
        )
        if len(cached_ids) >= article_count * 0.8:
            logger.info("extract_phrases_for_platform cache hit platform=%s cached=%d/%d",
                        platform, len(cached_ids), article_count)
            results = _build_results_from_db(articles, now)
            return {
                "platform": platform, "article_count": article_count,
                "batch_size": batch_size, "batches": 0,
                "estimated_timeout_seconds": estimated_timeout,
                "elapsed_seconds": round(_time.monotonic() - t0, 1),
                "results": results, "skipped_by_cache": True, "error": None,
            }

    # 3. 分批提取（平台内局部序号1-N）
    extractor = NewsPhraseExtractor()
    all_results: dict[int, dict] = {}  # article_id → result

    for batch_idx in range(batches_count):
        batch_start = batch_idx * batch_size
        batch_articles = articles[batch_start:batch_start + batch_size]
        batch_num = batch_idx + 1

        # 局部序号从1开始
        title_list = [(i + 1, a.title, a.id) for i, a in enumerate(batch_articles)]

        logger.info("  platform=%s batch=%d/%d titles=%d-%d",
                    platform, batch_num, batches_count,
                    batch_start + 1, batch_start + len(batch_articles))

        formatted = "\n".join(f"{seq}. {title}" for seq, title, _ in title_list)
        user_prompt = STAGE1_USER_PROMPT_TEMPLATE.format(
            count=len(title_list), titles=formatted
        )

        result, raw = _call_llm(
            extractor, STAGE1_SYSTEM_PROMPT, user_prompt,
            group=platform, batch_index=batch_num, analysis_time=now,
        )
        if not result:
            logger.error("  platform=%s batch=%d LLM returned None, skipping raw_preview=%s",
                         platform, batch_num, str(raw or "")[:120])
            continue

        has_critical, valid_items = _validate_stage1_result(
            result, title_list, batch_num, platform,
            user_prompt=user_prompt, raw_output=raw or "",
        )
        if has_critical:
            logger.warning("  platform=%s batch=%d validation failed, skipping", platform, batch_num)
            continue

        # 写库 + 收集结果
        from django.db import close_old_connections
        close_old_connections()
        for item in valid_items:
            seq = item.get("id")
            if seq is None or seq < 1 or seq > len(title_list):
                continue
            _, _, article_id = title_list[seq - 1]
            extracted = item.get("extracted_phrases", [])
            normalized = item.get("normalized_phrases", [])

            LLMPhraseExtraction.objects.update_or_create(
                article_id=article_id,
                analysis_time=now,
                defaults={
                    "extracted_phrases": json.dumps(extracted, ensure_ascii=False),
                    "normalized_phrases": json.dumps(normalized, ensure_ascii=False),
                }
            )
            all_results[article_id] = {
                "extracted_phrases": extracted,
                "normalized_phrases": normalized,
            }

    # 4. 组装返回结果（按文章顺序）
    results = []
    for a in articles:
        r = all_results.get(a.id, {"extracted_phrases": [], "normalized_phrases": []})
        results.append({
            "article_id":         a.id,
            "title":              a.title,
            "extracted_phrases":  r["extracted_phrases"],
            "normalized_phrases": r["normalized_phrases"],
        })

    elapsed = round(_time.monotonic() - t0, 1)
    logger.info("extract_phrases_for_platform done platform=%s articles=%d elapsed=%.1fs",
                platform, article_count, elapsed)

    return {
        "platform":                 platform,
        "article_count":            article_count,
        "batch_size":               batch_size,
        "batches":                  batches_count,
        "estimated_timeout_seconds": estimated_timeout,
        "elapsed_seconds":           elapsed,
        "results":                   results,
        "skipped_by_cache":          False,
        "error":                     None,
    }


def _build_results_from_db(articles: list, now) -> list:
    """从数据库读取已缓存的短语结果（缓存命中时用）。"""
    from datetime import timedelta
    article_ids = [a.id for a in articles]
    ext_map: dict[int, dict] = {}
    for ext in LLMPhraseExtraction.objects.filter(
        article_id__in=article_ids,
        analysis_time__gte=now - timedelta(hours=12),
    ).order_by("-analysis_time"):
        if ext.article_id not in ext_map:
            try:
                ext_map[ext.article_id] = {
                    "extracted_phrases": json.loads(ext.extracted_phrases or "[]"),
                    "normalized_phrases": json.loads(ext.normalized_phrases or "[]"),
                }
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("_build_results_from_db json parse error article_id=%d err=%s",
                               ext.article_id, e)
                ext_map[ext.article_id] = {"extracted_phrases": [], "normalized_phrases": []}

    results = []
    for a in articles:
        r = ext_map.get(a.id, {"extracted_phrases": [], "normalized_phrases": []})
        results.append({
            "article_id":         a.id,
            "title":              a.title,
            "extracted_phrases":  r["extracted_phrases"],
            "normalized_phrases": r["normalized_phrases"],
        })
    return results
