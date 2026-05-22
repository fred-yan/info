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
    "zaobao": "联合早报",
    "zhihu": "知乎",
    "weibo": "微博",
    "pengpai": "澎湃新闻",
    "economist": "The Economist",
    "apnews": "AP News",
    "washingtonpost": "Washington Post",
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

    keywords = []
    for r in results:
        prev_score = prev_scores.get(r.keyword)
        if prev_score is None:
            trend_direction = "rising"  # 新出现的关键词视为上升
        elif r.score > prev_score:
            trend_direction = "rising"
        elif r.score < prev_score:
            trend_direction = "falling"
        else:
            trend_direction = "stable"

        keywords.append({
            "keyword": r.keyword,
            "score": round(r.score, 2),
            "rank": r.rank,
            "count": r.count,
            "platform_count": r.platform_count,
            "coverage": round(r.coverage, 4),
            "sources": json.loads(r.sources),
            "sample_articles": json.loads(r.sample_articles),
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


def platforms_view(request):
    """
    GET /api/platforms/
    
    返回所有平台的元数据：标签、分组、最后抓取时间、文章总数。
    """
    if request.method != "GET":
        return HttpResponse(status=405)

    platform_groups = settings.PLATFORM_GROUPS

    # 获取每个平台的最后抓取时间和文章数
    platform_stats = Info.objects.values("platform").annotate(
        last_fetch=Max("date"),
        article_count=Count("id"),
    )

    stats_map = {s["platform"]: s for s in platform_stats}

    platforms = []
    for group_name, group_cfg in platform_groups.items():
        for platform_name in group_cfg["platforms"]:
            stats = stats_map.get(platform_name, {})
            last_fetch = stats.get("last_fetch")

            platforms.append({
                "name": platform_name,
                "label": PLATFORM_LABELS.get(platform_name, platform_name),
                "group": group_name,
                "last_fetch": last_fetch.strftime("%Y-%m-%dT%H:%M:%S") if last_fetch else None,
                "article_count": stats.get("article_count", 0),
            })

    return _json_response({
        "platforms": platforms,
    })
