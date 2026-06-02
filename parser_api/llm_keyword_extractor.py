"""
LLM 热点短语提取器
用大模型对中文新闻标题做短语提取和归纳，再基于权重评分体系计算热点排名。

两步流程：
  Step A: LLM 提取短语 → 存入 llm_phrase_extraction 表（可跳过，如果已有缓存）
  Step B: 从 llm_phrase_extraction 读取 → 聚合评分 → 存入 keyword_analysis/result
"""
import json
import logging
from collections import defaultdict

from django.conf import settings
from django.db import close_old_connections
from django.db.models import Max
from django.utils import timezone

from .models import Info, KeywordAnalysis, KeywordResult, LLMPhraseExtraction, LLMBatchLog
from .keyword_extractor import _calc_article_weight
from .llm_extractor_tiny import NewsPhraseExtractor, TitleInput

logger = logging.getLogger(__name__)


# ==================== 数据获取 ====================

def _get_recent_articles() -> dict[str, list]:
    """每个平台只取最近一批数据（MAX(date)）"""
    latest_dates = Info.objects.values('platform').annotate(latest=Max('date'))
    result = {}
    for item in latest_dates:
        batch = list(Info.objects.filter(
            platform=item['platform'], date=item['latest']
        ))
        if batch:
            result[item['platform']] = batch
    return result


def _prepare_titles(articles_by_platform: dict, platforms: list[str]):
    """
    去重并构建映射关系。
    """
    title_to_ids: dict[str, list[int]] = defaultdict(list)
    id_to_article: dict[int, Info] = {}

    for plat in platforms:
        for article in articles_by_platform.get(plat, []):
            title_to_ids[article.title].append(article.id)
            id_to_article[article.id] = article

    unique_titles = []
    seq_to_title = {}
    for seq, title in enumerate(title_to_ids.keys(), 1):
        unique_titles.append(TitleInput(id=str(seq), title=title))
        seq_to_title[seq] = title

    return unique_titles, title_to_ids, id_to_article, seq_to_title


# ==================== 缓存检查 ====================

def _check_cache(all_article_ids: set[int]) -> bool:
    """
    检查这批 article_ids 是否已经有 LLM 提取结果。
    只要所有 id 都在 llm_phrase_extraction 表中存在，就认为有缓存。
    """
    if not all_article_ids:
        return False
    cached_ids = set(
        LLMPhraseExtraction.objects.filter(
            article_id__in=all_article_ids
        ).values_list('article_id', flat=True).distinct()
    )
    return all_article_ids.issubset(cached_ids)


def _load_from_cache(all_article_ids: set[int], id_to_article: dict):
    """
    从 llm_phrase_extraction 表读取已有结果，重建 phrase_groups 结构。
    返回与 LLM 调用相同格式的 combined_result。
    """
    records = LLMPhraseExtraction.objects.filter(
        article_id__in=all_article_ids
    ).order_by('article_id', '-analysis_time')

    # 每个 article_id 只取最新一条
    seen_aids = set()
    aid_to_phrases: dict[int, list[str]] = {}
    aid_to_extracted: dict[int, list[str]] = {}
    items = []
    for rec in records:
        if rec.article_id in seen_aids:
            continue
        seen_aids.add(rec.article_id)
        np_list = json.loads(rec.normalized_phrases)
        ep_list = json.loads(rec.extracted_phrases)
        aid_to_phrases[rec.article_id] = np_list
        aid_to_extracted[rec.article_id] = ep_list
        items.append({
            "id": rec.article_id,
            "title": id_to_article.get(rec.article_id, Info()).title or "",
            "extracted_phrases": ep_list,
            "normalized_phrases": np_list,
        })

    # 重建 phrase_groups: normalized_phrase → {member_article_ids, surface_forms}
    phrase_to_aids: dict[str, set[int]] = defaultdict(set)
    for aid, phrases in aid_to_phrases.items():
        for p in phrases:
            phrase_to_aids[p].add(aid)

    phrase_groups = []
    for phrase, aids in phrase_to_aids.items():
        surface_forms = set()
        for aid in aids:
            surface_forms.update(aid_to_extracted.get(aid, []))
        phrase_groups.append({
            "normalized_phrase": phrase,
            "member_article_ids": sorted(aids),
            "surface_forms": sorted(surface_forms),
        })

    return {"items": items, "phrase_groups": phrase_groups, "from_cache": True}


# ==================== LLM 调用 ====================

def _call_llm_safe(extractor: NewsPhraseExtractor, titles: list,
                   group: str = "", batch_index: int = 0,
                   analysis_time=None) -> dict:
    """调用 LLM 并做容错处理，同时保存批次日志。"""
    from .llm_extractor_tiny import (
        SYSTEM_PROMPT_TEMPLATE, USER_PROMPT_TEMPLATE, ExtractionResult,
    )

    input_data = [{"id": t.id, "title": t.title} for t in titles]
    formatted = extractor._format_titles(titles)
    user_prompt = USER_PROMPT_TEMPLATE.format(titles=formatted)

    try:
        response = extractor.client.chat.completions.create(
            model=extractor.config.MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE},
                {"role": "user", "content": user_prompt},
            ],
            temperature=extractor.config.TEMPERATURE,
            max_tokens=extractor.config.MAX_TOKENS,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason

        # DeepSeek JSON Mode 有概率返回空 content，需要处理
        if not raw or not raw.strip():
            logger.warning("LLM returned empty content, retrying once...")
            # 重试一次
            response = extractor.client.chat.completions.create(
                model=extractor.config.MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_TEMPLATE},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=extractor.config.TEMPERATURE,
                max_tokens=extractor.config.MAX_TOKENS,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            if not raw or not raw.strip():
                raise ValueError("LLM returned empty content after retry")

        # 检查是否被截断
        if finish_reason == "length":
            logger.warning("LLM output truncated (finish_reason=length), tokens used: %s",
                          response.usage.completion_tokens if response.usage else "unknown")
            raise ValueError(f"Output truncated at {len(raw)} chars, need larger max_tokens or smaller batch")

        # 统计 token 使用
        if response.usage:
            logger.info(
                "LLM tokens: prompt=%d, completion=%d, total=%d",
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                response.usage.total_tokens,
            )

        result = json.loads(raw)

        try:
            validated = ExtractionResult(**result)
            parsed = validated.model_dump()
        except Exception as e:
            logger.warning("llm pydantic validation failed, using raw JSON: %s", e)
            parsed = {
                "items": result.get("items", []),
                "phrase_groups": result.get("phrase_groups", []),
            }

        # 保存批次日志
        if analysis_time:
            close_old_connections()
            LLMBatchLog.objects.create(
                analysis_time=analysis_time,
                group=group,
                batch_index=batch_index,
                title_count=len(titles),
                input_titles=json.dumps(input_data, ensure_ascii=False),
                output_raw=raw,
                success=True,
            )

        return parsed

    except Exception as e:
        logger.error("LLM call failed: %s", e)
        # 保存失败日志
        if analysis_time:
            close_old_connections()
            LLMBatchLog.objects.create(
                analysis_time=analysis_time,
                group=group,
                batch_index=batch_index,
                title_count=len(titles),
                input_titles=json.dumps(input_data, ensure_ascii=False),
                output_raw="",
                success=False,
                error_msg=str(e),
            )
        # 返回空结果，让流程继续处理其他批次
        return {"items": [], "phrase_groups": []}


def _save_batch_extractions(llm_result, seq_to_title, title_to_ids, analysis_time) -> int:
    """将一批 LLM 结果存入 llm_phrase_extraction 表。"""
    objs = []
    for item in llm_result.get("items", []):
        seq = item["id"]
        title = seq_to_title.get(seq)
        if not title:
            continue
        article_ids = title_to_ids.get(title, [])
        ep = json.dumps(item["extracted_phrases"], ensure_ascii=False)
        np_ = json.dumps(item["normalized_phrases"], ensure_ascii=False)
        for aid in article_ids:
            objs.append(LLMPhraseExtraction(
                article_id=aid,
                analysis_time=analysis_time,
                extracted_phrases=ep,
                normalized_phrases=np_,
            ))
    if objs:
        close_old_connections()
        LLMPhraseExtraction.objects.bulk_create(objs)
    return len(objs)


# ==================== 评分 ====================

def _score_phrase_groups(phrase_groups, id_to_article: dict, total_platforms: int,
                         from_cache: bool = False) -> list[dict]:
    """
    对 phrase_groups 做加权评分。
    phrase_groups 中 member_titles 或 member_article_ids 指向文章。
    - from_cache=False: member_titles 是 seq 编号，需要 seq_to_title + title_to_ids 映射
    - from_cache=True:  member_article_ids 直接是 article_id
    """
    scored = []
    for pg in phrase_groups:
        phrase = pg["normalized_phrase"]
        surface_forms = pg.get("surface_forms", [])

        # 收集关联的 article_ids
        if from_cache:
            article_ids = pg.get("member_article_ids", [])
        else:
            article_ids = pg.get("member_article_ids", pg.get("member_titles", []))

        if not article_ids:
            continue

        weighted_freq = 0.0
        platforms = set()
        sample_articles = []

        for aid in article_ids:
            art = id_to_article.get(aid)
            if not art:
                continue
            weight = _calc_article_weight(art)
            weighted_freq += weight
            platforms.add(art.platform)
            if len(sample_articles) < 3:
                sample_articles.append({
                    "title": art.title,
                    "url": art.url,
                    "platform": art.platform,
                })

        plat_count = len(platforms)
        coverage = plat_count / total_platforms if total_platforms else 0
        cross_site_boost = 1 + coverage * 3.0
        score = weighted_freq * cross_site_boost

        scored.append({
            "keyword": phrase,
            "score": round(score, 2),
            "count": len(article_ids),
            "platform_count": plat_count,
            "coverage": round(coverage, 4),
            "sources": sorted(platforms),
            "sample_articles": sample_articles,
            "surface_forms": surface_forms,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


# ==================== 主入口 ====================

BATCH_SIZE = 10  # 每批 10 条标题，避免输出超过 max_tokens 被截断


def extract_keywords_llm(group: str = "domestic", top: int = 50,
                          force: bool = False, batch_size: int | None = None) -> dict:
    """
    LLM 热点短语提取主入口。

    Args:
        group: "domestic" / "international"
        top: 返回前 N 个短语
        force: True 时跳过缓存，强制重新调用 LLM
        batch_size: 每批标题数量（None 则使用默认值 BATCH_SIZE）
    """
    effective_batch_size = batch_size or BATCH_SIZE
    cfg = settings.PLATFORM_GROUPS.get(group)
    if not cfg:
        return {"error": f"unknown group: {group}"}

    platforms = cfg["platforms"]
    label = cfg["label"]
    now = timezone.now()

    # Step 0: 获取数据
    articles_by_platform = _get_recent_articles()
    unique_titles, title_to_ids, id_to_article, seq_to_title = _prepare_titles(
        articles_by_platform, platforms
    )

    all_article_ids = set(id_to_article.keys())
    article_count = len(all_article_ids)
    active_platforms = [p for p in platforms if p in articles_by_platform]
    total_platforms = len(active_platforms)

    logger.info(
        "llm_extract group=%s articles=%d unique_titles=%d platforms=%d",
        group, article_count, len(unique_titles), total_platforms,
    )

    if not unique_titles:
        return {"error": "no articles found", "group": group}

    # Step A: 检查缓存 or 调用 LLM
    use_cache = (not force) and _check_cache(all_article_ids)

    if use_cache:
        logger.info("cache hit — loading from llm_phrase_extraction table")
        combined = _load_from_cache(all_article_ids, id_to_article)
        phrase_groups = combined["phrase_groups"]
    else:
        logger.info("cache miss — calling LLM in batches of %d", effective_batch_size)
        extractor = NewsPhraseExtractor()
        all_items = []
        all_phrase_groups = []

        for i in range(0, len(unique_titles), effective_batch_size):
            batch = unique_titles[i:i + effective_batch_size]
            batch_idx = i // effective_batch_size + 1
            logger.info("  batch %d-%d / %d", i + 1, i + len(batch), len(unique_titles))
            result = _call_llm_safe(extractor, batch,
                                     group=group, batch_index=batch_idx,
                                     analysis_time=now)
            all_items.extend(result.get("items", []))
            all_phrase_groups.extend(result.get("phrase_groups", []))

            # 保存到 llm_phrase_extraction 表
            batch_seq_to_title = {int(t.id): t.title for t in batch}
            close_old_connections()
            saved = _save_batch_extractions(result, batch_seq_to_title, title_to_ids, now)
            logger.info("  saved %d extraction records", saved)

        # 合并多批 phrase_groups（同名短语合并 member_titles）
        merged_pg: dict[str, dict] = {}
        for pg in all_phrase_groups:
            key = pg["normalized_phrase"]
            if key not in merged_pg:
                merged_pg[key] = {
                    "normalized_phrase": key,
                    "member_titles": [],
                    "surface_forms": list(set(pg.get("surface_forms", []))),
                }
            merged_pg[key]["member_titles"].extend(pg.get("member_titles", []))
            for sf in pg.get("surface_forms", []):
                if sf not in merged_pg[key]["surface_forms"]:
                    merged_pg[key]["surface_forms"].append(sf)

        # 将 seq 编号映射为 article_id
        phrase_groups = []
        for pg in merged_pg.values():
            aids = set()
            for seq in pg["member_titles"]:
                title = seq_to_title.get(seq)
                if title:
                    aids.update(title_to_ids.get(title, []))
            phrase_groups.append({
                "normalized_phrase": pg["normalized_phrase"],
                "member_article_ids": sorted(aids),
                "surface_forms": pg["surface_forms"],
            })

    # Step B: 评分
    scored = _score_phrase_groups(phrase_groups, id_to_article, total_platforms,
                                  from_cache=use_cache)
    top_keywords = scored[:top]

    # Step C: 写入 keyword_analysis / keyword_result
    close_old_connections()
    group_name = f"{group}_llm"
    analysis = KeywordAnalysis.objects.create(
        analysis_time=now,
        group=group_name,
        article_count=article_count,
        platform_count=total_platforms,
        platforms=json.dumps(active_platforms, ensure_ascii=False),
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

    logger.info(
        "llm_keyword_analysis group=%s articles=%d keywords=%d cached=%s",
        group_name, article_count, len(top_keywords), use_cache,
    )

    return {
        "analysis_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        group: {
            "label": label,
            "article_count": article_count,
            "unique_titles": len(unique_titles),
            "platform_count": total_platforms,
            "cached": use_cache,
            "keywords": top_keywords,
        },
    }
