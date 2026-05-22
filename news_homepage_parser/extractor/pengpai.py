"""澎湃新闻热榜获取器。

接口：https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar
提取 hotNews 字段，返回 rank, title, url
"""
import logging
import requests
from news_homepage_parser.models import NewsItem

logger = logging.getLogger(__name__)

_API = "https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar"
_BASE_URL = "https://www.thepaper.cn"
_TIMEOUT = 15
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def fetch_hot_news() -> tuple[bool, list[NewsItem] | str]:
    """
    返回 (True, items) 或 (False, error_message)。
    items 按接口原始顺序，包含 rank, title, url。
    """
    try:
        resp = requests.get(_API, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        hot_news = data.get("data", {}).get("hotNews", [])
    except Exception as e:
        logger.error("pengpai fetch hot_news failed error=%s", e, exc_info=True)
        return (False, f"Failed to fetch pengpai hot news: {e}")

    result = []
    for rank, story in enumerate(hot_news, start=1):
        try:
            title = story.get("name", "")
            cont_id = story.get("contId", "")
            if not title or not cont_id:
                continue
            url = f"{_BASE_URL}/newsDetail_forward_{cont_id}"
            result.append(NewsItem(
                title=title,
                link=url,
                section="hotlist",
                rank=rank,
                ranktime="24hour",
                detail={}
            ))
        except Exception:
            logger.debug("pengpai story parse failed rank=%d", rank, exc_info=True)
            continue

    logger.info("pengpai hot_news fetched count=%d", len(result))
    return (True, result)
