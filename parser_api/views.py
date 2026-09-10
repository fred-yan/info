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
from news_homepage_parser.extractor.huxiu import fetch_article_list as huxiu_fetch_article_list
from news_homepage_parser.extractor.jiqizhixin import fetch_articles as jiqizhixin_fetch_articles
from news_homepage_parser.extractor.cls import fetch_hot_articles as cls_fetch_hot_articles
from news_homepage_parser.extractor.wscn import fetch_hot_articles as wscn_fetch_hot_articles

from .site_config import SITE_URLS
from .models import Info

logger = logging.getLogger(__name__)


def _now_minute() -> object:
    """返回截断到分钟的当前时间，保证同批次所有记录 date 完全一致。"""
    return timezone.now().replace(second=0, microsecond=0)


def _get_batch_id(request) -> str:
    """从 request 里取调度器传入的 _batch_id，手动触发时为空字符串。"""
    return request.GET.get('_batch_id', '').strip()


def _bulk_save(platform: str, info_objects: list, url: str = "") -> None:
    """批量写入数据库，统一处理日志和空结果警告。"""
    if info_objects:
        close_old_connections()
        Info.objects.bulk_create(info_objects)
        logger.info("%s saved to db items=%d", platform, len(info_objects))
    else:
        logger.warning("%s result empty (0 items) url=%s", platform, url)


def _make_info(platform: str, item, fetch_time, batch_id: str, **overrides) -> Info:
    """统一构造 Info 对象，自动序列化 detail 字段并填入 batch_id。"""
    detail_str = json.dumps(item.detail, ensure_ascii=False) if item.detail else ""
    return Info(
        title=item.title,
        url=item.link,
        platform=platform,
        date=fetch_time,
        batch_id=batch_id,
        section=overrides.get('section', item.section or ""),
        rank=item.rank,
        detail=overrides.get('detail', detail_str),
        ranktime=overrides.get('ranktime', item.ranktime or ""),
    )


def economist_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["economist"]
    t0 = time.monotonic()
    logger.info("economist_view start url=%s", url)
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = []
            if result.items:
                for item in result.items:
                    info_objects.append(_make_info("economist", item, fetch_time, batch_id))
            if result.most_read:
                for item in result.most_read:
                    info_objects.append(_make_info("economist", item, fetch_time, batch_id,
                                                   section=item.section or "hotlist",
                                                   ranktime=item.ranktime or "48hour"))
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("economist saved to db items=%d most_read=%d",
                            len(result.items or []), len(result.most_read or []))
            else:
                logger.warning("economist result empty items=%d most_read=%d url=%s",
                               len(result.items or []), len(result.most_read or []), url)
        except Exception as db_exc:
            logger.error("economist db save error: %s", db_exc, exc_info=True)

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    if result.error is not None:
        logger.warning("economist parse failed url=%s error=%s", url, result.error)
    logger.info("view done url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def apnews_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["apnews"]
    t0 = time.monotonic()
    logger.info("apnews_view start url=%s", url)
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = []
            if result.items:
                for item in result.items:
                    info_objects.append(_make_info("apnews", item, fetch_time, batch_id, detail=""))
            if result.most_read:
                for item in result.most_read:
                    info_objects.append(_make_info("apnews", item, fetch_time, batch_id,
                                                   section=item.section or "hotlist",
                                                   ranktime=item.ranktime or "48hour",
                                                   detail=""))
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("apnews saved to db items=%d most_read=%d",
                            len(result.items or []), len(result.most_read or []))
        except Exception as db_exc:
            logger.error("apnews db save error: %s", db_exc, exc_info=True)

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    if result.error is not None:
        logger.warning("parse failed url=%s error=%s", url, result.error)
    logger.info("view done url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def ftchinese_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["ftchinese"]
    t0 = time.monotonic()
    logger.info("ftchinese_view start url=%s", url)
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None and result.items:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = [_make_info("ftchinese", item, fetch_time, batch_id)
                            for item in result.items]
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("ftchinese saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("ftchinese db save error: %s", db_exc, exc_info=True)

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    if result.error is not None:
        logger.warning("parse failed url=%s error=%s", url, result.error)
    logger.info("view done url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def wsj_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["wsj"]
    t0 = time.monotonic()
    logger.info("wsj_view start url=%s", url)
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None and result.items:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = [_make_info("wsj", item, fetch_time, batch_id)
                            for item in result.items]
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("wsj saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("wsj db save error: %s", db_exc, exc_info=True)

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    if result.error is not None:
        logger.warning("parse failed url=%s error=%s", url, result.error)
    logger.info("view done url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def kr36_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["kr36"]
    t0 = time.monotonic()
    logger.info("kr36_view start url=%s", url)
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None and result.items:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = [_make_info("kr36", item, fetch_time, batch_id)
                            for item in result.items]
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("kr36 saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("kr36 db save error: %s", db_exc, exc_info=True)

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    if result.error is not None:
        logger.warning("parse failed url=%s error=%s", url, result.error)
    logger.info("view done url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def huxiu_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    logger.info("huxiu_view start")
    t0 = time.monotonic()
    try:
        items = huxiu_fetch_article_list(page_size=20)
    except Exception as exc:
        logger.error("huxiu_view unhandled error: %s", exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    if items:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = [_make_info("huxiu", item, fetch_time, batch_id) for item in items]
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("huxiu saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("huxiu db save error: %s", db_exc, exc_info=True)

    elapsed = time.monotonic() - t0
    status = 200 if items else 502
    if not items:
        logger.warning("huxiu_view empty result elapsed=%.1fs", elapsed)
    logger.info("huxiu_view status=%d items=%d elapsed=%.1fs", status, len(items), elapsed)
    result_body = json.dumps({"status": "ok" if items else "error", "count": len(items)}, ensure_ascii=False)
    return HttpResponse(result_body, content_type="application/json", status=status)


def wscn_view(request):
    """华尔街见闻最热文章：直接调 awtmt.com API，无需 Playwright。"""
    if request.method != "GET":
        return HttpResponse(status=405)

    logger.info("wscn_view start")
    t0 = time.monotonic()
    try:
        items = wscn_fetch_hot_articles()
    except Exception as exc:
        logger.error("wscn_view unhandled error: %s", exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    if items:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = [_make_info("wscn", item, fetch_time, batch_id) for item in items]
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("wscn saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("wscn db save error: %s", db_exc, exc_info=True)

    elapsed = time.monotonic() - t0
    status = 200 if items else 502
    if not items:
        logger.warning("wscn_view empty result elapsed=%.1fs", elapsed)
    logger.info("wscn_view status=%d items=%d elapsed=%.1fs", status, len(items), elapsed)
    result_body = json.dumps({"status": "ok" if items else "error", "count": len(items)}, ensure_ascii=False)
    return HttpResponse(result_body, content_type="application/json", status=status)


def cls_view(request):
    """财联社热门文章排行榜：直接 HTTP 请求首页 HTML，无需 Playwright。"""
    if request.method != "GET":
        return HttpResponse(status=405)

    logger.info("cls_view start")
    t0 = time.monotonic()
    try:
        items = cls_fetch_hot_articles()
    except Exception as exc:
        logger.error("cls_view unhandled error: %s", exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    if items:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = [_make_info("cls", item, fetch_time, batch_id, detail="")
                            for item in items]
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("cls saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("cls db save error: %s", db_exc, exc_info=True)

    elapsed = time.monotonic() - t0
    status = 200 if items else 502
    if not items:
        logger.warning("cls_view empty result elapsed=%.1fs", elapsed)
    logger.info("cls_view status=%d items=%d elapsed=%.1fs", status, len(items), elapsed)
    result_body = json.dumps({"status": "ok" if items else "error", "count": len(items)}, ensure_ascii=False)
    return HttpResponse(result_body, content_type="application/json", status=status)


def jiqizhixin_view(request):
    """机器之心文章库：直接调内部 API，无需 Playwright。"""
    if request.method != "GET":
        return HttpResponse(status=405)

    logger.info("jiqizhixin_view start")
    t0 = time.monotonic()
    try:
        items = jiqizhixin_fetch_articles(page_size=15)
    except Exception as exc:
        logger.error("jiqizhixin_view unhandled error: %s", exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    if items:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = [_make_info("jiqizhixin", item, fetch_time, batch_id) for item in items]
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("jiqizhixin saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("jiqizhixin db save error: %s", db_exc, exc_info=True)

    elapsed = time.monotonic() - t0
    status = 200 if items else 502
    if not items:
        logger.warning("jiqizhixin_view empty result elapsed=%.1fs", elapsed)
    logger.info("jiqizhixin_view status=%d items=%d elapsed=%.1fs", status, len(items), elapsed)
    result_body = json.dumps({"status": "ok" if items else "error", "count": len(items)}, ensure_ascii=False)
    return HttpResponse(result_body, content_type="application/json", status=status)


def theverge_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)
    url = SITE_URLS["theverge"]
    t0 = time.monotonic()
    logger.info("theverge_view start url=%s", url)
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("theverge view error: %s", exc, exc_info=True)
        return HttpResponse(json.dumps({"error": str(exc)}), content_type="application/json", status=500)
    if result.error is None and result.items:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = [_make_info("theverge", i, fetch_time, batch_id, detail="")
                            for i in result.items]
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("theverge saved to db items=%d", len(info_objects))
        except Exception as e:
            logger.error("theverge db error: %s", e, exc_info=True)
    status = 200 if result.error is None else 502
    logger.info("theverge_view status=%d elapsed=%.1fs", status, time.monotonic() - t0)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def techcrunch_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)
    url = SITE_URLS["techcrunch"]
    t0 = time.monotonic()
    logger.info("techcrunch_view start url=%s", url)
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("techcrunch view error: %s", exc, exc_info=True)
        return HttpResponse(json.dumps({"error": str(exc)}), content_type="application/json", status=500)
    if result.error is None and result.items:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = [_make_info("techcrunch", i, fetch_time, batch_id, detail="")
                            for i in result.items]
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("techcrunch saved to db items=%d", len(info_objects))
        except Exception as e:
            logger.error("techcrunch db error: %s", e, exc_info=True)
    status = 200 if result.error is None else 502
    logger.info("techcrunch_view status=%d elapsed=%.1fs", status, time.monotonic() - t0)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def mittr_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)
    url = SITE_URLS["mittr"]
    t0 = time.monotonic()
    logger.info("mittr_view start url=%s", url)
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("mittr view error: %s", exc, exc_info=True)
        return HttpResponse(json.dumps({"error": str(exc)}), content_type="application/json", status=500)
    if result.error is None and result.items:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = [_make_info("mittr", i, fetch_time, batch_id, detail="")
                            for i in result.items]
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("mittr saved to db items=%d", len(info_objects))
        except Exception as e:
            logger.error("mittr db error: %s", e, exc_info=True)
    status = 200 if result.error is None else 502
    logger.info("mittr_view status=%d elapsed=%.1fs", status, time.monotonic() - t0)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def tmtpost_view(request):
    """钛媒体热文榜：Playwright 抓取，wait_after=6s 等 JS 渲染。"""
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["tmtpost"]
    t0 = time.monotonic()
    logger.info("tmtpost_view start url=%s", url)
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    if result.error is None and result.items:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = [_make_info("tmtpost", item, fetch_time, batch_id) for item in result.items]
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("tmtpost saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("tmtpost db save error: %s", db_exc, exc_info=True)

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    if result.error is not None:
        logger.warning("parse failed url=%s error=%s", url, result.error)
    logger.info("view done url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def wst_post_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["wst_post"]
    t0 = time.monotonic()
    logger.info("wst_post_view start url=%s", url)
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = []
            if result.items:
                for item in result.items:
                    info_objects.append(_make_info("washingtonpost", item, fetch_time, batch_id))
            if result.most_read:
                for item in result.most_read:
                    info_objects.append(_make_info("washingtonpost", item, fetch_time, batch_id,
                                                   section=item.section or "hotlist",
                                                   ranktime=item.ranktime or "48hour"))
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("washingtonpost saved to db items=%d most_read=%d",
                            len(result.items or []), len(result.most_read or []))
        except Exception as db_exc:
            logger.error("washingtonpost db save error: %s", db_exc, exc_info=True)

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    if result.error is not None:
        logger.warning("parse failed url=%s error=%s", url, result.error)
    logger.info("view done url=%s status=%d elapsed=%.1fs", url, status, elapsed)
    return HttpResponse(to_json(result), content_type="application/json", status=status)


def zaobao_view(request):
    if request.method != "GET":
        return HttpResponse(status=405)

    url = SITE_URLS["zaobao"]
    t0 = time.monotonic()
    logger.info("zaobao_view start url=%s", url)
    try:
        result = parse(url)
    except Exception as exc:
        logger.error("view unhandled error url=%s error=%s", url, exc, exc_info=True)
        body = json.dumps({"error": str(exc)})
        return HttpResponse(body, content_type="application/json", status=500)

    # 如果解析成功且没有错误，将数据存入数据库
    if result.error is None and result.items:
        try:
            fetch_time = _now_minute()
            batch_id = _get_batch_id(request)
            info_objects = [_make_info("zaobao", item, fetch_time, batch_id) for item in result.items]
            if info_objects:
                close_old_connections()
                Info.objects.bulk_create(info_objects)
                logger.info("zaobao saved to db items=%d", len(info_objects))
        except Exception as db_exc:
            logger.error("zaobao db save error: %s", db_exc, exc_info=True)

    status = 200 if result.error is None else 502
    elapsed = time.monotonic() - t0
    if result.error is not None:
        logger.warning("parse failed url=%s error=%s", url, result.error)
    logger.info("view done url=%s status=%d elapsed=%.1fs", url, status, elapsed)
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
    
    try:
        fetch_time = _now_minute()
        batch_id = _get_batch_id(request)
        info_objects = [_make_info("github", item, fetch_time, batch_id) for item in result]
        if info_objects:
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("github_trending saved to db since=%s items=%d", since, len(info_objects))
    except Exception as db_exc:
        logger.error("github_trending db save error: %s", db_exc, exc_info=True)
    
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

    try:
        fetch_time = _now_minute()
        batch_id = _get_batch_id(request)
        info_objects = [_make_info("zaobao", item, fetch_time, batch_id) for item in all_items]
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
    
    try:
        fetch_time = _now_minute()
        batch_id = _get_batch_id(request)
        info_objects = [_make_info("hackernews", item, fetch_time, batch_id) for item in result]
        if info_objects:
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("hacker_news_top_stories saved to db items=%d", len(info_objects))
    except Exception as db_exc:
        logger.error("hacker_news_top_stories db save error: %s", db_exc, exc_info=True)
    
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
    
    try:
        fetch_time = _now_minute()
        batch_id = _get_batch_id(request)
        info_objects = [_make_info("zhihu", item, fetch_time, batch_id) for item in result]
        if info_objects:
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("zhihu saved to db items=%d", len(info_objects))
    except Exception as db_exc:
        logger.error("zhihu db save error: %s", db_exc, exc_info=True)
    
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
    
    try:
        fetch_time = _now_minute()
        batch_id = _get_batch_id(request)
        info_objects = [_make_info("pengpai", item, fetch_time, batch_id) for item in result]
        if info_objects:
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("pengpai saved to db items=%d", len(info_objects))
    except Exception as db_exc:
        logger.error("pengpai db save error: %s", db_exc, exc_info=True)
    
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
    
    try:
        fetch_time = _now_minute()
        batch_id = _get_batch_id(request)
        info_objects = [_make_info("weibo", item, fetch_time, batch_id) for item in result]
        if info_objects:
            close_old_connections()
            Info.objects.bulk_create(info_objects)
            logger.info("weibo saved to db items=%d", len(info_objects))
    except Exception as db_exc:
        logger.error("weibo db save error: %s", db_exc, exc_info=True)
    
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
