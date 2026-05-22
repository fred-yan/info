import json
import time
import logging

from django.http import HttpResponse
from django.db import close_old_connections
from django.utils import timezone

from news_homepage_parser.parser import parse
from news_homepage_parser.pretty_printer import to_json
from news_homepage_parser.extractor.github_trending import fetch_trending
from news_homepage_parser.extractor.zaobao import fetch_hotlist_all as zaobao_fetch_hotlist_all
from news_homepage_parser.extractor.hacker_news import fetch_top_stories as hn_fetch_top_stories
from news_homepage_parser.extractor.zhihu import fetch_hot_list as zhihu_fetch_hot_list
from news_homepage_parser.extractor.pengpai import fetch_hot_news as pengpai_fetch_hot_news
from news_homepage_parser.extractor.weibo import fetch_hot_search as weibo_fetch_hot_search

from .site_config import SITE_URLS
from .models import Info

logger = logging.getLogger(__name__)


def _parse_site_view(request, url: str) -> HttpResponse:
    if request.method != "GET":
        return HttpResponse(status=405)

    t0 = time.monotonic()
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    logger.info("view response url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def economist_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["economist"]
    t0 = time.monotonic()
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None:
        try:
            # 将 fetched_at 转换为 Django 的 timezone-aware datetime
            fetch_time = timezone.make_aware(result.fetched_at) if timezone.is_naive(result.fetched_at) else result.fetched_at
            
            info_objects = []
            
            # 保存 items（section_1, section_2, section_3 和 Business 等栏目）
            if result.items:
                for item in result.items:
                    # 如果有 detail 字段，序列化为 JSON 字符串
                    detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
                    
                    info_objects.append(Info(
                        title=item.title,
                        url=item.link,
                        platform="economist",
                        date=fetch_time,
                        section=item.section or "",
                        rank=item.rank,
                        detail=detail_str,
                        ranktime=item.ranktime or ""
                    ))
            
            # 保存 most_read（hotlist，带 rank 和 ranktime）
            if result.most_read:
                for item in result.most_read:
                    # 如果有 detail 字段，序列化为 JSON 字符串
                    detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
                    
                    info_objects.append(Info(
                        title=item.title,
                        url=item.link,
                        platform="economist",
                        date=fetch_time,
                        section=item.section or "hotlist",
                        rank=item.rank,
                        detail=detail_str,
                        ranktime=item.ranktime or "48hour"
                    ))
            
            # 批量插入数据库
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("economist saved to db items=%d most_read=%d", len(result.items), len(result.most_read))
        except Exception as db_exc:
            logger.error("economist db save error: %s", db_exc, exc_info=True)
            # 数据库保存失败不影响 API 响应

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    logger.info("view response url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def apnews_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["apnews"]
    t0 = time.monotonic()
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None:
        try:
            # 将 fetched_at 转换为 Django 的 timezone-aware datetime
            fetch_time = timezone.make_aware(result.fetched_at) if timezone.is_naive(result.fetched_at) else result.fetched_at
            
            info_objects = []
            
            # 保存 items（section_1 和 section_2）
            if result.items:
                for item in result.items:
                    info_objects.append(Info(
                        title=item.title,
                        url=item.link,
                        platform="apnews",
                        date=fetch_time,
                        section=item.section or "",
                        rank=item.rank,
                        detail="",
                        ranktime=""
                    ))
            
            # 保存 most_read（hotlist，带 rank 和 ranktime）
            if result.most_read:
                for item in result.most_read:
                    info_objects.append(Info(
                        title=item.title,
                        url=item.link,
                        platform="apnews",
                        date=fetch_time,
                        section=item.section or "hotlist",  # section 为 hotlist
                        rank=item.rank,  # rank 字段
                        detail="",
                        ranktime=item.ranktime or "48hour"  # ranktime 字段
                    ))
            
            # 批量插入数据库
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("apnews saved to db items=%d most_read=%d", len(result.items), len(result.most_read))
        except Exception as db_exc:
            logger.error("apnews db save error: %s", db_exc, exc_info=True)
            # 数据库保存失败不影响 API 响应

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    logger.info("view response url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def ftchinese_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["ftchinese"]
    t0 = time.monotonic()
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None and result.items:
        try:
            # 将 fetched_at 转换为 Django 的 timezone-aware datetime
            fetch_time = timezone.make_aware(result.fetched_at) if timezone.is_naive(result.fetched_at) else result.fetched_at
            
            info_objects = []
            
            # 保存 items（hotlist 和 hotlist_paid）
            for item in result.items:
                # 如果有 detail 字段，序列化为 JSON 字符串
                detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
                
                info_objects.append(Info(
                    title=item.title,
                    url=item.link,
                    platform="ftchinese",
                    date=fetch_time,
                    section=item.section or "",
                    rank=item.rank,
                    detail=detail_str,
                    ranktime=item.ranktime or ""
                ))
            
            # 批量插入数据库
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("ftchinese saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("ftchinese db save error: %s", db_exc, exc_info=True)
            # 数据库保存失败不影响 API 响应

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    logger.info("view response url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def wsj_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["wsj"]
    t0 = time.monotonic()
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None and result.items:
        try:
            # 将 fetched_at 转换为 Django 的 timezone-aware datetime
            fetch_time = timezone.make_aware(result.fetched_at) if timezone.is_naive(result.fetched_at) else result.fetched_at
            
            info_objects = []
            
            # 保存 items（section_1 和 hotlist）
            for item in result.items:
                # 如果有 detail 字段，序列化为 JSON 字符串
                detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
                
                info_objects.append(Info(
                    title=item.title,
                    url=item.link,
                    platform="wsj",
                    date=fetch_time,
                    section=item.section or "",
                    rank=item.rank,
                    detail=detail_str,
                    ranktime=item.ranktime or ""
                ))
            
            # 批量插入数据库
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("wsj saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("wsj db save error: %s", db_exc, exc_info=True)
            # 数据库保存失败不影响 API 响应

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    logger.info("view response url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def kr36_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["kr36"]
    t0 = time.monotonic()
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None and result.items:
        try:
            # 将 fetched_at 转换为 Django 的 timezone-aware datetime
            fetch_time = timezone.make_aware(result.fetched_at) if timezone.is_naive(result.fetched_at) else result.fetched_at
            
            info_objects = []
            
            # 保存 items（hotlist，带 attr 区分榜单类型）
            for item in result.items:
                # 如果有 detail 字段，序列化为 JSON 字符串
                detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
                
                info_objects.append(Info(
                    title=item.title,
                    url=item.link,
                    platform="kr36",
                    date=fetch_time,
                    section=item.section or "",
                    rank=item.rank,
                    detail=detail_str,
                    ranktime=item.ranktime or ""
                ))
            
            # 批量插入数据库
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("kr36 saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("kr36 db save error: %s", db_exc, exc_info=True)
            # 数据库保存失败不影响 API 响应

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    logger.info("view response url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def huxiu_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["huxiu"]
    t0 = time.monotonic()
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None and result.items:
        try:
            # 将 fetched_at 转换为 Django 的 timezone-aware datetime
            fetch_time = timezone.make_aware(result.fetched_at) if timezone.is_naive(result.fetched_at) else result.fetched_at
            
            info_objects = []
            
            # 保存 items（hotlist 和 section_1）
            for item in result.items:
                # 如果有 detail 字段，序列化为 JSON 字符串
                detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
                
                info_objects.append(Info(
                    title=item.title,
                    url=item.link,
                    platform="huxiu",
                    date=fetch_time,
                    section=item.section or "",
                    rank=item.rank,
                    detail=detail_str,
                    ranktime=item.ranktime or ""
                ))
            
            # 批量插入数据库
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("huxiu saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("huxiu db save error: %s", db_exc, exc_info=True)
            # 数据库保存失败不影响 API 响应

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    logger.info("view response url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def wst_post_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["wst_post"]
    t0 = time.monotonic()
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None:
        try:
            # 将 fetched_at 转换为 Django 的 timezone-aware datetime
            fetch_time = timezone.make_aware(result.fetched_at) if timezone.is_naive(result.fetched_at) else result.fetched_at
            
            info_objects = []
            
            # 保存 items（section_1, section_2, section_3）
            if result.items:
                for item in result.items:
                    # 如果有 detail 字段，序列化为 JSON 字符串
                    detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
                    
                    info_objects.append(Info(
                        title=item.title,
                        url=item.link,
                        platform="washingtonpost",
                        date=fetch_time,
                        section=item.section or "",
                        rank=item.rank,
                        detail=detail_str,
                        ranktime=item.ranktime or ""
                    ))
            
            # 保存 most_read（hotlist，带 rank 和 ranktime）
            if result.most_read:
                for item in result.most_read:
                    # 如果有 detail 字段，序列化为 JSON 字符串
                    detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
                    
                    info_objects.append(Info(
                        title=item.title,
                        url=item.link,
                        platform="washingtonpost",
                        date=fetch_time,
                        section=item.section or "hotlist",
                        rank=item.rank,
                        detail=detail_str,
                        ranktime=item.ranktime or "48hour"
                    ))
            
            # 批量插入数据库
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("washingtonpost saved to db items=%d most_read=%d", len(result.items), len(result.most_read))
        except Exception as db_exc:
            logger.error("washingtonpost db save error: %s", db_exc, exc_info=True)
            # 数据库保存失败不影响 API 响应

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    logger.info("view response url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def zaobao_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["zaobao"]
    t0 = time.monotonic()
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None and result.items:
        try:
            # 将 fetched_at 转换为 Django 的 timezone-aware datetime
            fetch_time = timezone.make_aware(result.fetched_at) if timezone.is_naive(result.fetched_at) else result.fetched_at
            
            info_objects = []
            
            # 保存 items（section_1 和 finance）
            for item in result.items:
                # 如果有 detail 字段，序列化为 JSON 字符串
                detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
                
                info_objects.append(Info(
                    title=item.title,
                    url=item.link,
                    platform="zaobao",
                    date=fetch_time,
                    section=item.section or "",
                    rank=item.rank,
                    detail=detail_str,
                    ranktime=item.ranktime or ""
                ))
            
            # 批量插入数据库
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("zaobao saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("zaobao db save error: %s", db_exc, exc_info=True)
            # 数据库保存失败不影响 API 响应

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    logger.info("view response url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def github_trending_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)
    
    since = request.GET.get("since", "daily")
    t0 = time.monotonic()
    ok, result = fetch_trending(since)
    elapsed = time.monotonic() - t0
    
    if not ok:
        logger.warning("github_trending failed since=%s error=%s elapsed=%.1fs", since, result, elapsed)
        body = json.dumps({"error": result})
        return HttpResponse(body, content_type="application/json", status=400 if "Invalid" in result else 502)
    
    # 保存数据到数据库
    try:
        from django.utils import timezone as django_timezone
        from datetime import datetime, timezone as dt_timezone
        
        # 创建当前时间戳
        fetch_time = django_timezone.now()
        
        info_objects = []
        
        # 保存 items（hotlist，带 ranktime）
        for item in result:
            # 如果有 detail 字段，序列化为 JSON 字符串
            detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
            
            info_objects.append(Info(
                title=item.title,
                url=item.link,
                platform="github",
                date=fetch_time,
                section=item.section or "",
                rank=item.rank,
                detail=detail_str,
                ranktime=item.ranktime or ""
            ))
        
        # 批量插入数据库
        if info_objects:
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("github_trending saved to db since=%s items=%d", since, len(info_objects))
    except Exception as db_exc:
        logger.error("github_trending db save error: %s", db_exc, exc_info=True)
        # 数据库保存失败不影响 API 响应
    
    # 构建 JSON 响应
    response_data = {
        "since": since,
        "total": len(result),
        "items": [
            {
                "title": item.title,
                "link": item.link,
                "section": item.section,
                "rank": item.rank,
                "ranktime": item.ranktime,
                **({"detail": item.detail} if item.detail else {})
            }
            for item in result
        ]
    }
    
    logger.info("github_trending ok since=%s items=%d elapsed=%.1fs", since, len(result), elapsed)
    return HttpResponse(json.dumps(response_data, ensure_ascii=False, indent=2), content_type="application/json")


def zaobao_hotlist_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)
    t0 = time.monotonic()

    # 一次抓取，同时获取日榜和周榜
    ok, result = zaobao_fetch_hotlist_all()
    if not ok:
        elapsed = time.monotonic() - t0
        logger.warning("zaobao_hotlist failed error=%s elapsed=%.1fs", result, elapsed)
        body = json.dumps({"error": result})
        return HttpResponse(body, content_type="application/json", status=502)

    result_day = result["day"]
    result_week = result["week"]

    # 合并日榜和周榜
    all_items = result_day + result_week
    elapsed = time.monotonic() - t0

    # 保存数据到数据库
    try:
        fetch_time = timezone.now()
        info_objects = []

        for item in all_items:
            detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""

            info_objects.append(Info(
                title=item.title,
                url=item.link,
                platform="zaobao",
                date=fetch_time,
                section=item.section or "",
                rank=item.rank,
                detail=detail_str,
                ranktime=item.ranktime or ""
            ))

        if info_objects:
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("zaobao_hotlist saved to db day=%d week=%d", len(result_day), len(result_week))
    except Exception as db_exc:
        logger.error("zaobao_hotlist db save error: %s", db_exc, exc_info=True)

    # 构建 JSON 响应
    def _serialize(items):
        return [
            {
                "title": item.title,
                "link": item.link,
                "section": item.section,
                "rank": item.rank,
                "ranktime": item.ranktime,
                **({"detail": item.detail} if item.detail else {})
            }
            for item in items
        ]

    response_data = {
        "total": len(all_items),
        "day": {"total": len(result_day), "items": _serialize(result_day)},
        "week": {"total": len(result_week), "items": _serialize(result_week)},
    }

    logger.info("zaobao_hotlist ok day=%d week=%d elapsed=%.1fs", len(result_day), len(result_week), elapsed)
    return HttpResponse(json.dumps(response_data, ensure_ascii=False, indent=2), content_type="application/json")


def hacker_news_top_stories_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)
    t0 = time.monotonic()
    ok, result = hn_fetch_top_stories()
    elapsed = time.monotonic() - t0
    if not ok:
        logger.warning("hacker_news_top_stories failed error=%s elapsed=%.1fs", result, elapsed)
        body = json.dumps({"error": result})
        return HttpResponse(body, content_type="application/json", status=502)
    
    # 保存数据到数据库
    try:
        fetch_time = timezone.now()
        info_objects = []
        
        # 保存 items（hotlist，带 ranktime）
        for item in result:
            # 如果有 detail 字段，序列化为 JSON 字符串
            detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
            
            info_objects.append(Info(
                title=item.title,
                url=item.link,
                platform="hackernews",
                date=fetch_time,
                section=item.section or "",
                rank=item.rank,
                detail=detail_str,
                ranktime=item.ranktime or ""
            ))
        
        # 批量插入数据库
        if info_objects:
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("hacker_news_top_stories saved to db items=%d", len(info_objects))
    except Exception as db_exc:
        logger.error("hacker_news_top_stories db save error: %s", db_exc, exc_info=True)
        # 数据库保存失败不影响 API 响应
    
    # 构建 JSON 响应
    response_data = {
        "total": len(result),
        "items": [
            {
                "title": item.title,
                "link": item.link,
                "section": item.section,
                "rank": item.rank,
                "ranktime": item.ranktime,
                **({"detail": item.detail} if item.detail else {})
            }
            for item in result
        ]
    }
    
    logger.info("hacker_news_top_stories ok items=%d elapsed=%.1fs", len(result), elapsed)
    return HttpResponse(json.dumps(response_data, ensure_ascii=False, indent=2), content_type="application/json")


def zhihu_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)
    t0 = time.monotonic()
    ok, result = zhihu_fetch_hot_list()
    elapsed = time.monotonic() - t0
    if not ok:
        logger.warning("zhihu failed error=%s elapsed=%.1fs", result, elapsed)
        body = json.dumps({"error": result})
        return HttpResponse(body, content_type="application/json", status=502)
    
    # 保存数据到数据库
    try:
        fetch_time = timezone.now()
        info_objects = []
        
        # 保存 items（hotlist，带 ranktime）
        for item in result:
            # 如果有 detail 字段，序列化为 JSON 字符串
            detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
            
            info_objects.append(Info(
                title=item.title,
                url=item.link,
                platform="zhihu",
                date=fetch_time,
                section=item.section or "",
                rank=item.rank,
                detail=detail_str,
                ranktime=item.ranktime or ""
            ))
        
        # 批量插入数据库
        if info_objects:
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("zhihu saved to db items=%d", len(info_objects))
    except Exception as db_exc:
        logger.error("zhihu db save error: %s", db_exc, exc_info=True)
        # 数据库保存失败不影响 API 响应
    
    # 构建 JSON 响应
    response_data = {
        "total": len(result),
        "items": [
            {
                "title": item.title,
                "link": item.link,
                "section": item.section,
                "rank": item.rank,
                "ranktime": item.ranktime,
                **({"detail": item.detail} if item.detail else {})
            }
            for item in result
        ]
    }
    
    logger.info("zhihu ok items=%d elapsed=%.1fs", len(result), elapsed)
    return HttpResponse(json.dumps(response_data, ensure_ascii=False, indent=2), content_type="application/json")


def pengpai_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)
    t0 = time.monotonic()
    ok, result = pengpai_fetch_hot_news()
    elapsed = time.monotonic() - t0
    if not ok:
        logger.warning("pengpai failed error=%s elapsed=%.1fs", result, elapsed)
        body = json.dumps({"error": result})
        return HttpResponse(body, content_type="application/json", status=502)
    
    # 保存数据到数据库
    try:
        fetch_time = timezone.now()
        info_objects = []
        
        # 保存 items（hotlist，带 ranktime）
        for item in result:
            # 如果有 detail 字段，序列化为 JSON 字符串
            detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
            
            info_objects.append(Info(
                title=item.title,
                url=item.link,
                platform="pengpai",
                date=fetch_time,
                section=item.section or "",
                rank=item.rank,
                detail=detail_str,
                ranktime=item.ranktime or ""
            ))
        
        # 批量插入数据库
        if info_objects:
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("pengpai saved to db items=%d", len(info_objects))
    except Exception as db_exc:
        logger.error("pengpai db save error: %s", db_exc, exc_info=True)
        # 数据库保存失败不影响 API 响应
    
    # 构建 JSON 响应
    response_data = {
        "total": len(result),
        "items": [
            {
                "title": item.title,
                "link": item.link,
                "section": item.section,
                "rank": item.rank,
                "ranktime": item.ranktime,
                **({"detail": item.detail} if item.detail else {})
            }
            for item in result
        ]
    }
    
    logger.info("pengpai ok items=%d elapsed=%.1fs", len(result), elapsed)
    return HttpResponse(json.dumps(response_data, ensure_ascii=False, indent=2), content_type="application/json")


def weibo_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)
    t0 = time.monotonic()
    ok, result = weibo_fetch_hot_search()
    elapsed = time.monotonic() - t0
    if not ok:
        logger.warning("weibo failed error=%s elapsed=%.1fs", result, elapsed)
        body = json.dumps({"error": result})
        return HttpResponse(body, content_type="application/json", status=502)
    
    # 保存数据到数据库
    try:
        fetch_time = timezone.now()
        info_objects = []
        
        # 保存 items（hotlist，带 ranktime）
        for item in result:
            # 如果有 detail 字段，序列化为 JSON 字符串
            detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
            
            info_objects.append(Info(
                title=item.title,
                url=item.link,
                platform="weibo",
                date=fetch_time,
                section=item.section or "",
                rank=item.rank,
                detail=detail_str,
                ranktime=item.ranktime or ""
            ))
        
        # 批量插入数据库
        if info_objects:
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("weibo saved to db items=%d", len(info_objects))
    except Exception as db_exc:
        logger.error("weibo db save error: %s", db_exc, exc_info=True)
        # 数据库保存失败不影响 API 响应
    
    # 构建 JSON 响应
    response_data = {
        "total": len(result),
        "items": [
            {
                "title": item.title,
                "link": item.link,
                "section": item.section,
                "rank": item.rank,
                "ranktime": item.ranktime,
                **({"detail": item.detail} if item.detail else {})
            }
            for item in result
        ]
    }
    
    logger.info("weibo ok items=%d elapsed=%.1fs", len(result), elapsed)
    return HttpResponse(json.dumps(response_data, ensure_ascii=False, indent=2), content_type="application/json")



def keywords_view(request):
    """关键词分析接口"""
    if request.method != "GET":
        return HttpResponse(status=405)

    group = request.GET.get("group")  # domestic / international / None
    top = int(request.GET.get("top", 50))

    # 如果带 run=1 参数，立即执行一次分析
    if request.GET.get("run") == "1":
        from parser_api.keyword_extractor import extract_keywords
        result = extract_keywords(group=group, top=top)
        return HttpResponse(
            json.dumps(result, ensure_ascii=False, indent=2),
            content_type="application/json",
        )

    # 否则返回最近一次分析结果
    from parser_api.models import KeywordAnalysis, KeywordResult

    filters = {}
    if group:
        filters["group"] = group

    analyses = KeywordAnalysis.objects.filter(**filters).order_by("-analysis_time")

    # 取最新一批（同一 analysis_time 可能有 domestic + international 两条）
    if not analyses.exists():
        return HttpResponse(
            json.dumps({"error": "暂无分析结果，请先运行 extract_keywords 或访问 ?run=1"}, ensure_ascii=False),
            content_type="application/json",
            status=404,
        )

    latest_time = analyses.first().analysis_time
    latest_analyses = analyses.filter(analysis_time=latest_time)

    output = {"analysis_time": latest_time.strftime("%Y-%m-%d %H:%M:%S")}

    for a in latest_analyses:
        results = KeywordResult.objects.filter(analysis=a).order_by("rank")[:top]
        output[a.group] = {
            "label": a.group,
            "article_count": a.article_count,
            "platform_count": a.platform_count,
            "keywords": [
                {
                    "keyword": r.keyword,
                    "score": r.score,
                    "rank": r.rank,
                    "count": r.count,
                    "platform_count": r.platform_count,
                    "coverage": r.coverage,
                    "sources": json.loads(r.sources),
                    "sample_articles": json.loads(r.sample_articles),
                }
                for r in results
            ],
        }

    return HttpResponse(
        json.dumps(output, ensure_ascii=False, indent=2),
        content_type="application/json",
    )


def llm_keywords_view(request):
    """LLM 热点短语分析接口"""
    if request.method != "GET":
        return HttpResponse(status=405)

    group = request.GET.get("group", "domestic")
    top = int(request.GET.get("top", 50))

    # run=1 立即执行
    if request.GET.get("run") == "1":
        from parser_api.llm_keyword_extractor import extract_keywords_llm
        result = extract_keywords_llm(group=group, top=top)
        return HttpResponse(
            json.dumps(result, ensure_ascii=False, indent=2),
            content_type="application/json",
        )

    # 否则返回最近一次 LLM 分析结果
    from parser_api.models import KeywordAnalysis, KeywordResult

    grp_name = f"{group}_llm"
    analyses = KeywordAnalysis.objects.filter(group=grp_name).order_by("-analysis_time")

    if not analyses.exists():
        return HttpResponse(
            json.dumps({"error": "暂无 LLM 分析结果，请访问 ?run=1 执行"}, ensure_ascii=False),
            content_type="application/json",
            status=404,
        )

    latest = analyses.first()
    results = KeywordResult.objects.filter(analysis=latest).order_by("rank")[:top]

    output = {
        "analysis_time": latest.analysis_time.strftime("%Y-%m-%d %H:%M:%S"),
        "method": "llm",
        grp_name: {
            "label": latest.group,
            "article_count": latest.article_count,
            "platform_count": latest.platform_count,
            "keywords": [
                {
                    "keyword": r.keyword,
                    "score": r.score,
                    "rank": r.rank,
                    "count": r.count,
                    "platform_count": r.platform_count,
                    "coverage": r.coverage,
                    "sources": json.loads(r.sources),
                    "sample_articles": json.loads(r.sample_articles),
                }
                for r in results
            ],
        },
    }

    return HttpResponse(
        json.dumps(output, ensure_ascii=False, indent=2),
        content_type="application/json",
    )


def scheduler_status_view(request):
    """查看调度器状态和任务列表"""
    if request.method != "GET":
        return HttpResponse(status=405)
    
    from parser_api.scheduler import get_scheduler_status
    
    status_data = get_scheduler_status()
    
    return HttpResponse(
        json.dumps(status_data, ensure_ascii=False, indent=2),
        content_type="application/json"
    )
