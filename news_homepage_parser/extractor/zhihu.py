"""知乎热榜获取器。

接口：https://www.zhihu.com/api/v4/feed/topstory/hot-list-web?limit=20&desktop=true
取前 30 条，字段：rank, title, desc, url
"""
import logging
import requests
from news_homepage_parser.models import NewsItem

logger = logging.getLogger(__name__)

_API = "https://www.zhihu.com/api/v4/feed/topstory/hot-list-web"
_TOP_N = 30
_TIMEOUT = 10
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.zhihu.com/",
    "x-api-version": "3.0.91",
}


def fetch_hot_list() -> tuple[bool, list[NewsItem] | str]:
    """
    返回 (True, items) 或 (False, error_message)。
    items 按接口原始顺序（热度降序），最多 30 条。
    """
    try:
        resp = requests.get(
            _API,
            params={"limit": _TOP_N, "desktop": "true"},
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
    except Exception as e:
        logger.error("zhihu fetch hot_list failed error=%s", e, exc_info=True)
        return (False, f"Failed to fetch zhihu hot list: {e}")

    result = []
    for rank, story in enumerate(data[:_TOP_N], start=1):
        try:
            target = story.get("target", {})
            title = target.get("title_area", {}).get("text", "")
            desc = target.get("excerpt_area", {}).get("text", "")
            url = target.get("link", {}).get("url", "")
            if not title:
                continue
            
            # desc 放入 detail
            detail = {"desc": desc} if desc else {}
            
            result.append(NewsItem(
                title=title,
                link=url,
                section="hotlist",
                rank=rank,
                ranktime="24hour",
                detail=detail
            ))
        except Exception:
            logger.debug("zhihu story parse failed rank=%d", rank, exc_info=True)
            continue

    logger.info("zhihu hot_list fetched count=%d", len(result))
    return (True, result)
