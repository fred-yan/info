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


# ==================== 校验函数 ====================

def _validate_stage1_result(
    result: dict,
    batch: list,          # [(seq, title, article_id), ...]
    batch_idx: int,
    group: str,
) -> tuple[bool, list[dict]]:
    """
    对阶段1单批 LLM 输出进行形式化校验。
    返回 (has_critical_error, valid_items)。
    严重错误 → has_critical_error=True，建议整批重试。
    警告 → 记录日志，过滤问题条目后继续。
    """
    items = result.get("items", [])
    seq_to_title = {seq: title for seq, title, _ in batch}
    errors: list[str] = []
    warnings: list[str] = []
    valid_items: list[dict] = []
    seen_ids: set[int] = set()

    # ── A: 数量完整性校验 ──────────────────────────────────────
    expected_count = len(batch)
    actual_count = len(items)
    if actual_count != expected_count:
        errors.append(
            f"[A] 数量不符: 输入{expected_count}条，输出{actual_count}条"
        )

    # ── B: 序号一致性 + 标题回溯校验 ───────────────────────────
    expected_ids = set(seq_to_title.keys())
    for item in items:
        seq = item.get("id")
        if seq is None:
            warnings.append("[B] 存在 id=null 的条目，已跳过")
            continue
        if seq < 1 or seq > len(batch):
            warnings.append(f"[B] id={seq} 超出范围 [1,{len(batch)}]，已跳过")
            continue
        if seq in seen_ids:
            warnings.append(f"[B] id={seq} 重复出现，已跳过")
            continue
        seen_ids.add(seq)

        # 标题回溯：title 字段必须与输入原标题一致
        output_title = (item.get("title") or "").strip()
        expected_title = seq_to_title[seq]
        if output_title and output_title != expected_title:
            warnings.append(
                f"[B] id={seq} 标题不符: 输出='{output_title[:40]}' "
                f"期望='{expected_title[:40]}' → 已修正"
            )
            # 修正：强制用正确标题（不阻断，但替换）
            item = dict(item)
            item["title"] = expected_title

        valid_items.append(item)

    # 缺失序号
    missing_ids = expected_ids - seen_ids
    if missing_ids:
        errors.append(f"[A] 缺失序号: {sorted(missing_ids)}")

    # ── C: 短语来源校验（警告级别）────────────────────────────
    for item in valid_items:
        seq = item.get("id")
        title = seq_to_title.get(seq, "")
        for phrase in item.get("extracted_phrases", []):
            if phrase and len(phrase) > 1 and phrase not in title:
                warnings.append(
                    f"[C] id={seq} extracted_phrase '{phrase}' "
                    f"不在原标题中（可能为规范化产物，仅记录）"
                )
                break  # 每条最多报一次，避免刷屏

    # ── D: 空短语率检测 ─────────────────────────────────────
    empty_count = sum(
        1 for item in valid_items
        if not item.get("extracted_phrases")
    )
    if valid_items and empty_count > len(valid_items) * 0.3:
        warnings.append(
            f"[D] 空短语率过高: {empty_count}/{len(valid_items)} 条无短语"
        )

    # ── 记录日志 ─────────────────────────────────────────────
    prefix = f"Stage1 batch={batch_idx} group={group}"
    has_critical = bool(errors)

    if errors:
        for err in errors:
            logger.error("%s 校验严重错误: %s", prefix, err)
    if warnings:
        for w in warnings:
            logger.warning("%s 校验警告: %s", prefix, w)
    if not errors and not warnings:
        logger.info("%s 校验通过 valid_items=%d", prefix, len(valid_items))
    elif not errors:
        logger.info("%s 校验通过（含警告） valid_items=%d", prefix, len(valid_items))

    return has_critical, valid_items


def _validate_stage2_result(
    result: dict,
    input_phrase_count: int,
    known_phrases: set[str],
    batch_num: int,
    group: str,
) -> tuple[bool, list[dict]]:
    """
    对阶段2单批 LLM 输出进行形式化校验。
    返回 (has_critical_error, valid_groups)。
    """
    groups = result.get("phrase_groups", [])
    errors: list[str] = []
    warnings: list[str] = []
    valid_groups: list[dict] = []
    seen_representatives: set[str] = set()

    # ── E-5: 组数量合理性 ────────────────────────────────────
    min_expected = max(5, int(input_phrase_count * 0.15))
    if len(groups) < min_expected:
        errors.append(
            f"[E5] phrase_groups 过少: 输入{input_phrase_count}个短语，"
            f"仅得到{len(groups)}组（期望≥{min_expected}组），可能被截断或过度合并"
        )

    for g in groups:
        rep = (g.get("representative") or "").strip()
        members = g.get("members") or []
        item_errors: list[str] = []

        # ── E-1: 代表词不能为空 ───────────────────────────────
        if not rep:
            warnings.append("[E1] 存在空 representative 的组，已跳过")
            continue

        # ── E-2: 代表词重复 ───────────────────────────────────
        if rep in seen_representatives:
            warnings.append(f"[E2] 代表词重复: '{rep}'，已跳过")
            continue
        seen_representatives.add(rep)

        # ── E-3: members 不能为空 ─────────────────────────────
        if not members:
            warnings.append(f"[E3] '{rep}' 的 members 为空，已跳过")
            continue

        # ── E-4: 至少一个成员是已知短语（防幻觉）──────────────
        valid_members = [m for m in members if m in known_phrases]
        if not valid_members:
            warnings.append(
                f"[E4] '{rep}' 的所有成员均不在阶段1短语库中 "
                f"members={members}，可能是幻觉，已跳过"
            )
            continue

        valid_groups.append(g)

    # ── 记录日志 ─────────────────────────────────────────────
    prefix = f"Stage2 batch={batch_num} group={group}"
    has_critical = bool(errors)

    if errors:
        for err in errors:
            logger.error("%s 校验严重错误: %s", prefix, err)
    if warnings:
        for w in warnings:
            logger.warning("%s 校验警告: %s", prefix, w)
    if not errors and not warnings:
        logger.info("%s 校验通过 valid_groups=%d", prefix, len(valid_groups))
    elif not errors:
        logger.info("%s 校验通过（含警告） valid_groups=%d", prefix, len(valid_groups))

    return has_critical, valid_groups


# ==================== 主流程 ====================

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

    # Check cache
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
        title_list = [(i + 1, title, aid) for i, (title, aid) in enumerate(unique_titles)]

        for batch_start in range(0, len(title_list), effective_batch_size):
            batch = title_list[batch_start:batch_start + effective_batch_size]
            batch_idx = batch_start // effective_batch_size + 1

            logger.info("  Stage 1 batch %d: titles %d-%d / %d",
                       batch_idx, batch_start + 1, batch_start + len(batch), len(title_list))

            formatted = "\n".join(f"{seq}. {title}" for seq, title, _ in batch)
            user_prompt = STAGE1_USER_PROMPT_TEMPLATE.format(
                count=len(batch), titles=formatted
            )

            result = _call_llm(extractor, STAGE1_SYSTEM_PROMPT, user_prompt,
                              group=group, batch_index=batch_idx, analysis_time=now)
            if not result:
                continue

            # ── 校验阶段1输出 ──────────────────────────────────
            has_critical, valid_items = _validate_stage1_result(
                result, batch, batch_idx, group
            )
            if has_critical:
                logger.warning(
                    "Stage 1 batch %d 校验严重失败，跳过本批次（不写库）", batch_idx
                )
                continue

            close_old_connections()
            for item in valid_items:
                seq = item.get("id")
                if seq is None or seq < 1 or seq > len(batch):
                    continue
                article_id = batch[seq - 1][2]

                LLMPhraseExtraction.objects.update_or_create(
                    article_id=article_id,
                    analysis_time=now,
                    defaults={
                        "extracted_phrases": json.dumps(
                            item.get("extracted_phrases", []), ensure_ascii=False),
                        "normalized_phrases": json.dumps(
                            item.get("normalized_phrases", []), ensure_ascii=False),
                    }
                )

    # === Stage 2: Global phrase grouping ===
    logger.info("Stage 2: global phrase grouping")

    if use_cache:
        extractions = LLMPhraseExtraction.objects.filter(
            analysis_time__gte=now - timedelta(hours=12),
        )
    else:
        extractions = LLMPhraseExtraction.objects.filter(
            article_id__in=all_article_ids,
            analysis_time=now,
        )

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

    STAGE2_MIN_FREQ = 2
    STAGE2_MAX_PHRASES = 300
    STAGE2_BATCH_SIZE = 150

    sorted_phrases = [
        (phrase, aids)
        for phrase, aids in sorted(phrase_to_article_ids.items(), key=lambda x: -len(x[1]))
        if len(aids) >= STAGE2_MIN_FREQ
    ][:STAGE2_MAX_PHRASES]

    known_phrases = {phrase for phrase, _ in sorted_phrases}

    logger.info("  Stage 2 using top %d phrases (batch_size=%d)",
                len(sorted_phrases), STAGE2_BATCH_SIZE)

    all_phrase_groups_raw = []
    for batch_start in range(0, len(sorted_phrases), STAGE2_BATCH_SIZE):
        batch = sorted_phrases[batch_start:batch_start + STAGE2_BATCH_SIZE]
        batch_num = batch_start // STAGE2_BATCH_SIZE + 1
        logger.info("  Stage 2 batch %d: phrases %d-%d / %d",
                    batch_num, batch_start + 1, batch_start + len(batch), len(sorted_phrases))

        phrase_lines = [
            f'  "{phrase}" → 文章ID: [{", ".join(str(i) for i in sorted(aids)[:10])}]'
            for phrase, aids in batch
        ]
        stage2_user = STAGE2_USER_PROMPT_TEMPLATE.format(
            total_titles=len(unique_titles),
            phrase_list="\n".join(phrase_lines),
        )

        close_old_connections()
        extractor = NewsPhraseExtractor()
        stage2_result = _call_llm(extractor, STAGE2_SYSTEM_PROMPT, stage2_user,
                                  group=group, batch_index=900 + batch_num, analysis_time=now)
        if not stage2_result:
            continue

        # ── 校验阶段2输出 ──────────────────────────────────────
        has_critical, valid_groups = _validate_stage2_result(
            stage2_result,
            input_phrase_count=len(batch),
            known_phrases=known_phrases,
            batch_num=batch_num,
            group=group,
        )
        if has_critical:
            logger.warning(
                "Stage 2 batch %d 校验严重失败（组数过少），跳过本批次", batch_num
            )
            continue

        all_phrase_groups_raw.extend(valid_groups)
        logger.info("  Stage 2 batch %d: %d valid groups", batch_num, len(valid_groups))

    logger.info("  Stage 2 total valid groups: %d", len(all_phrase_groups_raw))

    # Save phrase groups
    phrase_groups = []
    if all_phrase_groups_raw:
        close_old_connections()
        LLMPhraseGroup.objects.filter(analysis_time=now, group=group_name).delete()

        for pg in all_phrase_groups_raw:
            representative = pg.get("representative", "")
            members = pg.get("members", [])
            title_ids = pg.get("title_ids", [])

            all_aids = set()
            for member in members:
                all_aids.update(phrase_to_article_ids.get(member, set()))
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

    close_old_connections()
    analysis = KeywordAnalysis.objects.create(
        analysis_time=now,
        group=group_name,
        article_count=article_count,
        platform_count=total_platforms,
        platforms=json.dumps(
            [p for p in platforms if p in articles_by_platform], ensure_ascii=False),
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

            # Format titles for LLM — include count so prompt constraint is explicit
            formatted = "\n".join(f"{seq}. {title}" for seq, title, _ in batch)
            user_prompt = STAGE1_USER_PROMPT_TEMPLATE.format(
                count=len(batch), titles=formatted
            )

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
        # Cache hit: read by time window only (don't restrict by article_id,
        # because new fetches may have created new article IDs since Stage 1 ran)
        extractions = LLMPhraseExtraction.objects.filter(
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

    # Filter by frequency: only keep phrases appearing ≥2 times (removes 66% singleton noise).
    # Singletons ("花儿与少年4" etc.) have no hotspot value and waste tokens.
    STAGE2_MIN_FREQ = 2
    STAGE2_MAX_PHRASES = 300  # hard cap after frequency filter
    STAGE2_BATCH_SIZE = 150   # one call since model supports 384K output tokens

    sorted_phrases = [
        (phrase, aids)
        for phrase, aids in sorted(phrase_to_article_ids.items(), key=lambda x: -len(x[1]))
        if len(aids) >= STAGE2_MIN_FREQ
    ][:STAGE2_MAX_PHRASES]

    logger.info("  Stage 2 using top %d phrases (batch_size=%d)",
                len(sorted_phrases), STAGE2_BATCH_SIZE)

    # Process in batches, collect all phrase_groups
    all_phrase_groups_raw = []
    for batch_start in range(0, len(sorted_phrases), STAGE2_BATCH_SIZE):
        batch = sorted_phrases[batch_start:batch_start + STAGE2_BATCH_SIZE]
        batch_num = batch_start // STAGE2_BATCH_SIZE + 1
        logger.info("  Stage 2 batch %d: phrases %d-%d / %d",
                    batch_num, batch_start + 1, batch_start + len(batch), len(sorted_phrases))

        phrase_lines = []
        for phrase, aids in batch:
            ids_str = ", ".join(str(i) for i in sorted(aids)[:10])
            phrase_lines.append(f'  "{phrase}" → 文章ID: [{ids_str}]')

        phrase_list_str = "\n".join(phrase_lines)
        stage2_user = STAGE2_USER_PROMPT_TEMPLATE.format(
            total_titles=len(unique_titles),
            phrase_list=phrase_list_str,
        )

        close_old_connections()
        extractor = NewsPhraseExtractor()
        stage2_result = _call_llm(extractor, STAGE2_SYSTEM_PROMPT, stage2_user,
                                  group=group, batch_index=900 + batch_num, analysis_time=now)
        if stage2_result and "phrase_groups" in stage2_result:
            all_phrase_groups_raw.extend(stage2_result["phrase_groups"])
            logger.info("  Stage 2 batch %d: got %d groups", batch_num,
                        len(stage2_result["phrase_groups"]))

    logger.info("  Stage 2 total raw groups: %d", len(all_phrase_groups_raw))

    # Save phrase groups from all batches
    phrase_groups = []
    if all_phrase_groups_raw:
        close_old_connections()
        LLMPhraseGroup.objects.filter(analysis_time=now, group=group_name).delete()

        for pg in all_phrase_groups_raw:
            representative = pg.get("representative", "")
            members = pg.get("members", [])
            title_ids = pg.get("title_ids", [])

            all_aids = set()
            for member in members:
                all_aids.update(phrase_to_article_ids.get(member, set()))
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
