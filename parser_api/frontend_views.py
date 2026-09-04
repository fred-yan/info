"""
前端 API 视图
为 news-hotspot-frontend 提供优化的 API 端点。
"""
import json
import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Max, Count
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

from .models import Info, KeywordAnalysis, KeywordResult

logger = logging.getLogger(__name__)

# 平台标签映射
PLATFORM_LABELS = {
    "ftchinese": "FT中文网",
    "wsj": "华尔街日报中文版",
    "kr36": "36氪",
    "huxiu": "虎嗅",
    "tmtpost": "钛媒体",
    "jiqizhixin": "机器之心",
    "cls": "财联社",
    "wscn": "华尔街见闻",
    "zaobao": "联合早报",
    "zhihu": "知乎",
    "weibo": "微博",
    "pengpai": "澎湃新闻",
    "economist": "The Economist",
    "apnews": "AP News",
    "washingtonpost": "Washington Post",
    "theverge": "The Verge",
    "techcrunch": "TechCrunch",
    "mittr": "MIT Technology Review",
    "github": "GitHub Trending",
    "hackernews": "Hacker News",
}


def _json_response(data, status=200):
    """统一 JSON 响应"""
    return JsonResponse(data, status=status, json_dumps_params={"ensure_ascii": False})


def _error_response(message, status=400):
    """统一错误响应"""
    return _json_response({"error": message}, status=status)


def _llm_group(group: str) -> str:
    """将前端传入的 group 映射为 LLM 分析的数据库 group 值"""
    return f"{group}_llm"


def keywords_ranking_view(request):
    """
    GET /api/keywords/ranking/?group={domestic|international}
    
    返回关键词排名列表，包含趋势方向。
    通过比较最近两次分析结果计算趋势。
    使用 LLM 方案的分析结果。
    """
    if request.method != "GET":
        return HttpResponse(status=405)

    group = request.GET.get("group", "domestic")
    top = int(request.GET.get("top", "50"))

    if group not in ("domestic", "international"):
        return _error_response("group 参数必须为 domestic 或 international")

    db_group = _llm_group(group)

    # 获取最近两次分析
    analyses = KeywordAnalysis.objects.filter(
        group=db_group
    ).order_by("-analysis_time")[:2]

    if not analyses.exists():
        return _error_response("暂无分析结果", status=404)

    latest = analyses[0]
    previous = analyses[1] if len(analyses) > 1 else None

    # 获取最新排名结果
    results = KeywordResult.objects.filter(
        analysis=latest
    ).order_by("rank")[:top]

    # 获取上一次的分数用于计算趋势
    prev_scores = {}
    if previous:
        prev_results = KeywordResult.objects.filter(analysis=previous)
        prev_scores = {r.keyword: r.score for r in prev_results}

    # 预取 sample_articles 里用到的文章 URL → 阶段1短语映射，用于透明性展示
    from .models import LLMPhraseExtraction, Info as InfoModel
    # Collect all article URLs from sample_articles across all results
    all_sample_urls: set[str] = set()
    raw_samples: dict[str, list] = {}
    for r in results:
        sa = json.loads(r.sample_articles)
        raw_samples[r.keyword] = sa
        for a in sa:
            if a.get("url"):
                all_sample_urls.add(a["url"])

    # URL → article_id mapping
    url_to_id: dict[str, int] = {}
    if all_sample_urls:
        for info in InfoModel.objects.filter(url__in=list(all_sample_urls)).only("id", "url"):
            url_to_id[info.url] = info.id

    # article_id → normalized_phrases mapping (latest extraction within 24h)
    from django.utils import timezone as tz
    from datetime import timedelta
    since = tz.now() - timedelta(hours=24)
    id_to_phrases: dict[int, list[str]] = {}
    if url_to_id:
        for ext in LLMPhraseExtraction.objects.filter(
            article_id__in=list(url_to_id.values()),
            analysis_time__gte=since,
        ).order_by("-analysis_time"):
            if ext.article_id not in id_to_phrases:
                try:
                    id_to_phrases[ext.article_id] = json.loads(ext.normalized_phrases or "[]")
                except (json.JSONDecodeError, TypeError):
                    id_to_phrases[ext.article_id] = []

    keywords = []
    for r in results:
        prev_score = prev_scores.get(r.keyword)
        if prev_score is None:
            trend_direction = "rising"
        elif r.score > prev_score:
            trend_direction = "rising"
        elif r.score < prev_score:
            trend_direction = "falling"
        else:
            trend_direction = "stable"

        # Enrich sample_articles with the phrases extracted from each article
        enriched_samples = []
        for a in raw_samples.get(r.keyword, []):
            url = a.get("url", "")
            aid = url_to_id.get(url)
            phrases = id_to_phrases.get(aid, []) if aid else []
            enriched_samples.append({
                **a,
                "matched_phrases": phrases,  # 该文章阶段1提取出的短语，便于判断关联是否合理
            })

        keywords.append({
            "keyword": r.keyword,
            "score": round(r.score, 2),
            "rank": r.rank,
            "count": r.count,
            "platform_count": r.platform_count,
            "coverage": round(r.coverage, 4),
            "sources": json.loads(r.sources),
            "sample_articles": enriched_samples,
            "trend_direction": trend_direction,
        })

    return _json_response({
        "analysis_time": latest.analysis_time.strftime("%Y-%m-%d %H:%M:%S"),
        "group": group,
        "keywords": keywords,
    })


def keywords_trend_view(request):
    """
    GET /api/keywords/trend/?keyword={kw}&group={domestic|international}&days=7
    
    返回关键词在过去 N 天的历史分数（每次分析一个数据点）。
    """
    if request.method != "GET":
        return HttpResponse(status=405)

    keyword = request.GET.get("keyword")
    group = request.GET.get("group", "domestic")
    days = int(request.GET.get("days", "7"))

    if not keyword:
        return _error_response("keyword 参数必填")

    if group not in ("domestic", "international"):
        return _error_response("group 参数必须为 domestic 或 international")

    db_group = _llm_group(group)

    # 查询过去 N 天的分析结果
    since = timezone.now() - timedelta(days=days)

    analyses = KeywordAnalysis.objects.filter(
        group=db_group,
        analysis_time__gte=since,
    ).order_by("analysis_time")

    data_points = []
    for analysis in analyses:
        result = KeywordResult.objects.filter(
            analysis=analysis,
            keyword=keyword,
        ).first()

        if result:
            data_points.append({
                "timestamp": analysis.analysis_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "score": round(result.score, 2),
            })

    return _json_response({
        "keyword": keyword,
        "group": group,
        "days": days,
        "data_points": data_points,
    })


def keywords_articles_view(request):
    """
    GET /api/keywords/articles/?keyword={kw}&group={domestic|international}
    
    返回与关键词关联的文章列表。
    从最新分析的 sample_articles 获取基础数据，
    并从 Info 表补充完整信息。
    """
    if request.method != "GET":
        return HttpResponse(status=405)

    keyword = request.GET.get("keyword")
    group = request.GET.get("group", "domestic")

    if not keyword:
        return _error_response("keyword 参数必填")

    if group not in ("domestic", "international"):
        return _error_response("group 参数必须为 domestic 或 international")

    db_group = _llm_group(group)

    # 获取最新分析中该关键词的结果
    latest_analysis = KeywordAnalysis.objects.filter(
        group=db_group
    ).order_by("-analysis_time").first()

    if not latest_analysis:
        return _error_response("暂无分析结果", status=404)

    result = KeywordResult.objects.filter(
        analysis=latest_analysis,
        keyword=keyword,
    ).first()

    if not result:
        return _json_response({
            "keyword": keyword,
            "articles": [],
        })

    # 解析 sample_articles
    sample_articles = json.loads(result.sample_articles)

    # 从 Info 表中查找匹配的文章以获取完整信息
    # 使用平台分组中的平台列表
    platform_groups = settings.PLATFORM_GROUPS
    platforms = platform_groups.get(group, {}).get("platforms", [])

    # 在最近 7 天的文章中搜索包含关键词的标题
    since = timezone.now() - timedelta(days=7)
    matching_articles = Info.objects.filter(
        platform__in=platforms,
        date__gte=since,
        title__icontains=keyword,
    ).order_by("-date")[:100]

    articles = []
    seen_urls = set()

    # 先添加 sample_articles 中的文章
    for sa in sample_articles:
        url = sa.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            articles.append({
                "id": 0,
                "title": sa.get("title", ""),
                "url": url,
                "platform": sa.get("platform", ""),
                "section": "",
                "date": latest_analysis.analysis_time.strftime("%Y-%m-%dT%H:%M:%S"),
            })

    # 补充 Info 表中的匹配文章
    for info in matching_articles:
        if info.url not in seen_urls:
            seen_urls.add(info.url)
            articles.append({
                "id": info.id,
                "title": info.title,
                "url": info.url,
                "platform": info.platform,
                "section": info.section,
                "date": info.date.strftime("%Y-%m-%dT%H:%M:%S"),
            })

    return _json_response({
        "keyword": keyword,
        "articles": articles,
    })


def news_feed_view(request):
    """
    GET /api/news/feed/?platform={p}&section={s}&page={n}&page_size={size}
    
    分页文章流，支持平台和栏目过滤。
    """
    if request.method != "GET":
        return HttpResponse(status=405)

    # 解析参数
    platform = request.GET.get("platform")  # 逗号分隔的平台列表
    section = request.GET.get("section")
    page = int(request.GET.get("page", "1"))
    page_size = int(request.GET.get("page_size", "20"))

    # 限制 page_size
    page_size = min(page_size, 100)
    page = max(page, 1)

    # 构建查询
    queryset = Info.objects.all()

    if platform:
        platforms = [p.strip() for p in platform.split(",") if p.strip()]
        if platforms:
            queryset = queryset.filter(platform__in=platforms)

    if section:
        queryset = queryset.filter(section=section)

    # 按时间倒序
    queryset = queryset.order_by("-date", "-id")

    # 计算总数和分页
    total = queryset.count()
    offset = (page - 1) * page_size
    articles_qs = queryset[offset:offset + page_size]

    articles = []
    for info in articles_qs:
        articles.append({
            "id": info.id,
            "title": info.title,
            "url": info.url,
            "platform": info.platform,
            "section": info.section,
            "date": info.date.strftime("%Y-%m-%dT%H:%M:%S"),
        })

    has_next = (offset + page_size) < total

    return _json_response({
        "articles": articles,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": has_next,
    })


def _cron_to_interval_label(cron: str) -> str:
    """
    将 cron 表达式转成中文更新频率描述。
    只处理项目中实际使用的几种模式。
    """
    if not cron:
        return "定时更新"
    parts = cron.split()
    if len(parts) != 5:
        return "定时更新"
    minute, hour = parts[0], parts[1]
    # "0 6,12,18,0 * * *"  → 每6小时
    if ',' in hour:
        count = len(hour.split(','))
        interval = 24 // count
        return f"每{interval}小时更新"
    # "*/30 * * * *"  → 每30分钟
    if minute.startswith('*/'):
        n = minute[2:]
        return f"每{n}分钟更新"
    # "0 */6 * * *"  → 每6小时
    if hour.startswith('*/'):
        n = hour[2:]
        return f"每{n}小时更新"
    # "0 8 * * *"  → 每天
    return "每天更新"


def platforms_view(request):
    """
    GET /api/platforms/

    返回所有平台的元数据：标签、分组、最后抓取时间、文章总数、更新频率。
    """
    if request.method != "GET":
        return HttpResponse(status=405)

    platform_groups = settings.PLATFORM_GROUPS
    scheduler_config = getattr(settings, 'SCHEDULER_CONFIG', {})

    # 获取每个平台的最后抓取时间和文章数
    platform_stats = Info.objects.values("platform").annotate(
        last_fetch=Max("date"),
        article_count=Count("id"),
    )

    stats_map = {s["platform"]: s for s in platform_stats}

    # 构建 platform → cron 映射
    # task_name 与 platform name 可能不同（如 hacker_news vs hackernews，github_trending_daily vs github）
    # 使用显式别名表 + 前缀匹配双重查找
    _TASK_PLATFORM_ALIAS = {
        'hacker_news': 'hackernews',
        'zaobao_hotlist': 'zaobao',
        'github_trending_daily': 'github',
        'github_trending_weekly': 'github',
        'github_trending_monthly': 'github',
    }
    platform_cron_map: dict[str, str] = {}
    for task_name, cfg in scheduler_config.items():
        if not cfg.get('enabled', True):
            continue
        cron = cfg.get('cron', '')
        # First: check explicit alias
        aliased = _TASK_PLATFORM_ALIAS.get(task_name)
        if aliased and aliased not in platform_cron_map:
            platform_cron_map[aliased] = cron
            continue
        # Then: check if task_name matches a platform name directly or by prefix
        for group_cfg in platform_groups.values():
            for pname in group_cfg["platforms"]:
                if task_name == pname or task_name.startswith(pname + '_'):
                    if pname not in platform_cron_map:
                        platform_cron_map[pname] = cron

    platforms = []
    for group_name, group_cfg in platform_groups.items():
        for platform_name in group_cfg["platforms"]:
            stats = stats_map.get(platform_name, {})
            last_fetch = stats.get("last_fetch")
            cron = platform_cron_map.get(platform_name, '')
            update_interval = _cron_to_interval_label(cron)

            platforms.append({
                "name": platform_name,
                "label": PLATFORM_LABELS.get(platform_name, platform_name),
                "group": group_name,
                "last_fetch": last_fetch.strftime("%Y-%m-%dT%H:%M:%S+00:00") if last_fetch else None,
                "article_count": stats.get("article_count", 0),
                "update_interval": update_interval,
            })

    return _json_response({
        "platforms": platforms,
    })


# ── ranktime → 卡片标题映射 ────────────────────────────────────────────────────
_RANKTIME_LABELS: dict[str, str] = {
    "24hour":  "24小时热榜",
    "48hour":  "48小时热榜",
    "168hour": "周热榜",
    "720hour": "月热榜",
    "":        "热榜",
}

# ranktime 排序优先级（时间窗口由短到长）
_RT_ORDER = ["24hour", "48hour", "168hour", "720hour", ""]

# 超过此小时数认为数据陈旧（每天抓 4 次，正常间隔 6h，25h = 4 次全失败）
_STALE_HOURS = 25


def news_latest_view(request):
    """
    GET /api/news/latest/?platform={platform}

    返回指定平台最近一次抓取的数据。
    每个 (section分组 + ranktime) 彻底拆成独立卡片，返回平铺的 cards 列表。

    分组规则：
      - section != "hotlist" → 独立一张卡片，card_id="section"，card_title="平台名 · 首页资讯"
      - section == "hotlist" → 按 ranktime 各自一张卡片，card_title="平台名 · 24小时热榜" 等
    每张卡片内部：
      - 按 URL 去重（保留最高 rank 的那条）
      - 去重后重新按 1,2,3... 编号 index 字段

    响应 card 结构：
    {
      "card_id":       "section" | "hotlist_24hour" | ...,
      "card_title":    "FT中文网 · 首页资讯",
      "platform":      "ftchinese",
      "platform_label":"FT中文网",
      "fetch_time":    "2026-09-03T06:00:00",
      "fetch_age_hours": 2.5,
      "is_stale":      false,
      "articles": [
        {"index": 1, "id": 123, "title": "...", "url": "...", "section": "...", "ranktime": "..."}
      ]
    }
    """
    if request.method != "GET":
        return HttpResponse(status=405)

    platform = request.GET.get("platform", "").strip()
    if not platform:
        return _error_response("platform 参数必填")

    # 1. 取该平台最近一次抓取时间
    from django.db.models import Max
    agg = Info.objects.filter(platform=platform).aggregate(latest=Max("date"))
    latest_date = agg.get("latest")

    if latest_date is None:
        return _error_response(f"平台 '{platform}' 暂无数据", status=404)

    # 2. 时效性判断
    now = timezone.now()
    age_seconds = (now - latest_date).total_seconds()
    fetch_age_hours = round(age_seconds / 3600, 1)
    is_stale = fetch_age_hours > _STALE_HOURS

    platform_label = PLATFORM_LABELS.get(platform, platform)
    fetch_time_str = latest_date.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    # 3. 取该批次全部记录，按 section / rank / id 排序
    articles_qs = list(
        Info.objects.filter(
            platform=platform,
            date=latest_date,
        ).order_by("section", "rank", "id")
    )

    # 4. 分组：non_hotlist → section分组；hotlist → 按 ranktime 分
    #    key: ("section", "") 或 ("hotlist", ranktime)
    groups: dict[tuple[str, str], list] = {}

    for article in articles_qs:
        if article.section != "hotlist":
            key = ("section", "")
        else:
            rt = article.ranktime or ""
            key = ("hotlist", rt)
        groups.setdefault(key, []).append(article)

    # 5. 对每组做 URL 去重 + 重新编号
    def _dedup_and_index(items: list) -> list[dict]:
        seen_urls: set[str] = set()
        result = []
        for item in items:
            url = (item.url or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            result.append({
                "index":   len(result) + 1,   # 去重后重新编号
                "id":      item.id,
                "title":   item.title,
                "url":     url,
                "section": item.section,
                "rank":    item.rank,
                "ranktime": item.ranktime or "",
            })
        return result

    # 6. 构建 cards，按固定顺序输出
    def _card_meta(key: tuple[str, str]) -> tuple[str, str]:
        """返回 (card_id, card_title)"""
        group_type, rt = key
        if group_type == "section":
            return "section", f"{platform_label} · 首页资讯"
        else:
            label = _RANKTIME_LABELS.get(rt, f"热榜({rt})")
            cid = f"hotlist_{rt}" if rt else "hotlist"
            return cid, f"{platform_label} · {label}"

    def _sort_key(key: tuple[str, str]) -> tuple[int, int]:
        group_type, rt = key
        g = 0 if group_type == "section" else 1
        r = _RT_ORDER.index(rt) if rt in _RT_ORDER else len(_RT_ORDER)
        return (g, r)

    cards = []
    for key in sorted(groups.keys(), key=_sort_key):
        articles = _dedup_and_index(groups[key])
        if not articles:
            continue
        card_id, card_title = _card_meta(key)
        cards.append({
            "card_id":        card_id,
            "card_title":     card_title,
            "platform":       platform,
            "platform_label": platform_label,
            "fetch_time":     fetch_time_str,
            "fetch_age_hours": fetch_age_hours,
            "is_stale":       is_stale,
            "articles":       articles,
        })

    if not cards:
        return _error_response(f"平台 '{platform}' 暂无数据", status=404)

    if is_stale:
        return _error_response(
            f"平台 '{platform}' 数据已过期（{fetch_age_hours} 小时前）",
            status=503,
        )

    return _json_response({"cards": cards})
