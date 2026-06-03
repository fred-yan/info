"""
LLM 热点短语提取 V2 - 两阶段流程
阶段1: 分批逐条短语提取（存入 llm_phrase_extraction）
阶段2: 全局短语归纳（存入 llm_phrase_group）
最终: 评分写入 keyword_analysis + keyword_result
"""
import json
import logging
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections
from django.db.models import Max
from django.utils import timezone

from .models import Info, KeywordAnalysis, KeywordResult, LLMPhraseExtraction, LLMPhraseGroup, LLMBatchLog
from .llm_extractor_tiny import NewsPhraseExtractor, LLMConfig
from .llm_prompts import (
    STAGE1_SYSTEM_PROMPT, STAGE1_USER_PROMPT_TEMPLATE,
    STAGE2_SYSTEM_PROMPT, STAGE2_USER_PROMPT_TEMPLATE,
)
from .keyword_extractor import _calc_article_weight

logger = logging.getLogger(__name__)

BATCH_SIZE = LLMConfig.BATCH_SIZE  # 从 llm_config.ini 读取，默认 10


def extract_keywords_llm_v2(group: str = "domestic", top: int = 50,
                             force: bool = False, batch_size: int | None = None) -> dict:
    """Two-stage LLM extraction pipeline."""
    effective_batch_size = batch_size or BATCH_SIZE
    cfg = settings.PLATFORM_GROUPS.get(group)
    if not cfg:
        return {"error": f"unknown group: {group}"}

    platforms = cfg["platforms"]
    label = cfg["label"]
    now = timezone.now()
    group_name = f"{group}_llm"

    # === Get articles ===
    articles_by_platform = _get_recent_articles(platforms)
    id_to_article = {}
    unique_titles = []
    title_to_ids = defaultdict(list)

    for plat in platforms:
        for article in articles_by_platform.get(plat, []):
            if article.title and article.title.strip():
                title = article.title.strip()
                id_to_article[article.id] = article
                if title not in title_to_ids or article.id not in title_to_ids[title]:
                    title_to_ids[title].append(article.id)
                if title not in [t for t, _ in unique_titles]:
                    unique_titles.append((title, article.id))

    article_count = sum(len(v) for v in articles_by_platform.values())
    total_platforms = len([p for p in platforms if p in articles_by_platform])

    if not unique_titles:
        return {"error": "no articles found", "group": group}

    logger.info("v2_extract group=%s articles=%d unique_titles=%d platforms=%d",
                group, article_count, len(unique_titles), total_platforms)

    # === Stage 1: Extract phrases per article ===
    all_article_ids = set(id_to_article.keys())

    # Check cache: if all articles already have extractions for this analysis window
    use_cache = False
    if not force:
        cached_count = LLMPhraseExtraction.objects.filter(
            article_id__in=all_article_ids,
            analysis_time__gte=now - timedelta(hours=12),
        ).values('article_id').distinct().count()
        if cached_count >= len(all_article_ids) * 0.8:
            use_cache = True
            logger.info("Stage 1 cache hit: %d/%d articles", cached_count, len(all_article_ids))

    if not use_cache:
        logger.info("Stage 1: extracting phrases in batches of %d", effective_batch_size)
        extractor = NewsPhraseExtractor()

        # Build title list with global IDs
        title_list = [(i + 1, title, aid) for i, (title, aid) in enumerate(unique_titles)]

        for batch_start in range(0, len(title_list), effective_batch_size):
            batch = title_list[batch_start:batch_start + effective_batch_size]
            batch_idx = batch_start // effective_batch_size + 1

            logger.info("  Stage 1 batch %d: titles %d-%d / %d",
                       batch_idx, batch_start + 1, batch_start + len(batch), len(title_list))

            # Format titles for LLM
            formatted = "\n".join(f"{seq}. {title}" for seq, title, _ in batch)
            user_prompt = STAGE1_USER_PROMPT_TEMPLATE.format(titles=formatted)

            # Call LLM
            result = _call_llm(extractor, STAGE1_SYSTEM_PROMPT, user_prompt,
                              group=group, batch_index=batch_idx, analysis_time=now)

            if not result:
                continue

            # Save to llm_phrase_extraction
            close_old_connections()
            items = result.get("items", [])
            for item in items:
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

    # === Stage 2: Global phrase grouping ===
    logger.info("Stage 2: global phrase grouping")

    # Read all Stage 1 results from DB
    if use_cache:
        extractions = LLMPhraseExtraction.objects.filter(
            article_id__in=all_article_ids,
            analysis_time__gte=now - timedelta(hours=12),
        )
    else:
        extractions = LLMPhraseExtraction.objects.filter(
            article_id__in=all_article_ids,
            analysis_time=now,
        )

    # Build phrase → article_ids mapping
    phrase_to_article_ids = defaultdict(set)
    for ext in extractions:
        try:
            phrases = json.loads(ext.normalized_phrases)
        except (json.JSONDecodeError, TypeError):
            continue
        for phrase in phrases:
            if phrase:
                phrase_to_article_ids[phrase].add(ext.article_id)

    if not phrase_to_article_ids:
        return {"error": "no phrases extracted", "group": group}

    logger.info("  Total unique phrases: %d", len(phrase_to_article_ids))

    # Format for Stage 2 LLM call
    phrase_lines = []
    for phrase, aids in sorted(phrase_to_article_ids.items(), key=lambda x: -len(x[1])):
        ids_str = ", ".join(str(i) for i in sorted(aids)[:10])  # Limit to first 10 IDs for brevity
        phrase_lines.append(f'  "{phrase}" → 文章ID: [{ids_str}]')

    phrase_list_str = "\n".join(phrase_lines)
    stage2_user = STAGE2_USER_PROMPT_TEMPLATE.format(
        total_titles=len(unique_titles),
        phrase_list=phrase_list_str,
    )

    # Call LLM for Stage 2
    close_old_connections()
    extractor = NewsPhraseExtractor()
    stage2_result = _call_llm(extractor, STAGE2_SYSTEM_PROMPT, stage2_user,
                              group=group, batch_index=999, analysis_time=now)

    # Save phrase groups
    phrase_groups = []
    if stage2_result and "phrase_groups" in stage2_result:
        close_old_connections()
        # Delete old groups for this analysis
        LLMPhraseGroup.objects.filter(analysis_time=now, group=group_name).delete()

        for pg in stage2_result["phrase_groups"]:
            representative = pg.get("representative", "")
            members = pg.get("members", [])
            title_ids = pg.get("title_ids", [])

            # title_ids from LLM are article IDs
            # Collect all article_ids from members' phrase_to_article_ids
            all_aids = set()
            for member in members:
                all_aids.update(phrase_to_article_ids.get(member, set()))
            # Also add any directly referenced IDs
            for tid in title_ids:
                if tid in id_to_article:
                    all_aids.add(tid)

            if not all_aids:
                continue

            aids_list = sorted(all_aids)
            LLMPhraseGroup.objects.create(
                analysis_time=now,
                group=group_name,
                representative=representative,
                members=json.dumps(members, ensure_ascii=False),
                article_ids=json.dumps(aids_list),
                article_count=len(aids_list),
            )
            phrase_groups.append({
                "representative": representative,
                "members": members,
                "article_ids": aids_list,
                "article_count": len(aids_list),
            })

    # === Final: Score and write to keyword_analysis + keyword_result ===
    logger.info("Final: scoring %d phrase groups", len(phrase_groups))

    scored = []
    for pg in phrase_groups:
        aids = pg["article_ids"]
        # Calculate weighted frequency
        weighted_freq = 0.0
        platforms_seen = set()
        sample_articles = []

        for aid in aids:
            article = id_to_article.get(aid)
            if not article:
                continue
            weighted_freq += _calc_article_weight(article)
            platforms_seen.add(article.platform)
            if len(sample_articles) < 3:
                sample_articles.append({
                    "title": article.title,
                    "url": article.url,
                    "platform": article.platform,
                })

        plat_count = len(platforms_seen)
        coverage = plat_count / total_platforms if total_platforms > 0 else 0
        cross_site_boost = 1 + coverage * 3.0
        score = weighted_freq * cross_site_boost

        scored.append({
            "keyword": pg["representative"],
            "score": round(score, 2),
            "count": len(aids),
            "platform_count": plat_count,
            "coverage": round(coverage, 4),
            "sources": sorted(platforms_seen),
            "sample_articles": sample_articles,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_keywords = scored[:top]

    # Write to keyword_analysis + keyword_result
    close_old_connections()
    analysis = KeywordAnalysis.objects.create(
        analysis_time=now,
        group=group_name,
        article_count=article_count,
        platform_count=total_platforms,
        platforms=json.dumps([p for p in platforms if p in articles_by_platform], ensure_ascii=False),
    )

    for idx, kw in enumerate(top_keywords, 1):
        KeywordResult.objects.create(
            analysis=analysis,
            keyword=kw["keyword"],
            score=kw["score"],
            rank=idx,
            count=kw["count"],
            platform_count=kw["platform_count"],
            coverage=kw["coverage"],
            sources=json.dumps(kw["sources"], ensure_ascii=False),
            sample_articles=json.dumps(kw["sample_articles"], ensure_ascii=False),
        )

    logger.info("v2_extract done group=%s keywords=%d", group_name, len(top_keywords))

    return {
        "analysis_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "method": "llm_v2",
        group_name: {
            "label": label,
            "article_count": article_count,
            "platform_count": total_platforms,
            "keywords": top_keywords,
        },
    }


def _get_recent_articles(platforms: list[str]) -> dict[str, list]:
    """Get the latest batch of articles per platform."""
    result = {}
    for plat in platforms:
        latest = Info.objects.filter(platform=plat).aggregate(latest=Max('date'))['latest']
        if latest:
            batch = list(Info.objects.filter(platform=plat, date=latest))
            if batch:
                result[plat] = batch
    return result


def _call_llm(extractor: NewsPhraseExtractor, system_prompt: str, user_prompt: str,
              group: str = "", batch_index: int = 0, analysis_time=None) -> dict | None:
    """Call LLM with retry and error handling."""
    try:
        response = extractor.client.chat.completions.create(
            model=extractor.config.MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=extractor.config.TEMPERATURE,
            max_tokens=extractor.config.MAX_TOKENS,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason

        # Log token usage
        if response.usage:
            logger.info("LLM tokens: prompt=%d, completion=%d, total=%d",
                       response.usage.prompt_tokens, response.usage.completion_tokens,
                       response.usage.total_tokens)

        # Handle empty content
        if not raw or not raw.strip():
            logger.warning("LLM returned empty content, retrying...")
            response = extractor.client.chat.completions.create(
                model=extractor.config.MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=extractor.config.TEMPERATURE,
                max_tokens=extractor.config.MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            if not raw or not raw.strip():
                logger.error("LLM returned empty after retry")
                return None

        if finish_reason == "length":
            logger.warning("LLM output truncated (finish_reason=length)")
            return None

        result = json.loads(raw)

        # Save batch log
        if analysis_time:
            close_old_connections()
            LLMBatchLog.objects.create(
                analysis_time=analysis_time,
                group=group,
                batch_index=batch_index,
                title_count=0,
                input_titles="",
                output_raw=raw[:5000],  # Truncate for storage
                success=True,
            )

        return result

    except Exception as e:
        logger.error("LLM call failed: %s", e)
        if analysis_time:
            try:
                close_old_connections()
                LLMBatchLog.objects.create(
                    analysis_time=analysis_time,
                    group=group,
                    batch_index=batch_index,
                    title_count=0,
                    input_titles="",
                    output_raw="",
                    success=False,
                    error_msg=str(e),
                )
            except Exception:
                pass
        return None
