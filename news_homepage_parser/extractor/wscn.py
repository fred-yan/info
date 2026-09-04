"""
华尔街见闻最热文章提取器

API: https://api-one-wscn.awtmt.com/apiv1/content/articles/hot?period=all
返回当日最热文章列表（day_items），按阅读量降序排列，无需认证。

返回结构：
{
  "data": {
    "day_items": [
      {
        "id": 3780885,
        "title": "油价涨势暂歇缓解通胀担忧...",
        "uri": "https://wallstreetcn.com/articles/3780885",
        "display_time": 1788385407,
        "pageviews": 156312,
        "comment_count": 0
      }
    ]
  }
}
"""
import json
import logging
import urllib.request
import urllib.error

from news_homepage_parser.models import NewsItem

logger = logging.getLogger(__name__)

_API_URL = "https://api-one-wscn.awtmt.com/apiv1/content/articles/hot?period=all"


def fetch_hot_articles() -> list[NewsItem]:
    """
    调用华尔街见闻热文 API，返回当日最热文章列表。
    section="hotlist", ranktime="24hour", rank=列表顺序(按 pageviews 降序)。
    """
    req = urllib.request.Request(
        _API_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://wallstreetcn.com/",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://wallstreetcn.com",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.error("wscn api http error: %s", e)
        return []
    except Exception as e:
        logger.error("wscn api error: %s", e)
        return []

    if data.get("code") != 20000:
        logger.warning("wscn api non-200 code: %s", data.get("code"))
        return []

    day_items = data.get("data", {}).get("day_items", [])
    if not day_items:
        logger.warning("wscn api: day_items is empty")
        return []

    items: list[NewsItem] = []
    for rank, article in enumerate(day_items, start=1):
        title = (article.get("title") or "").strip()
        uri = (article.get("uri") or "").strip()
        if not title or not uri:
            continue

        pageviews = article.get("pageviews", 0)
        detail = {"pageviews": pageviews} if pageviews else None

        items.append(NewsItem(
            title=title,
            link=uri,
            section="hotlist",
            rank=rank,
            ranktime="24hour",
            detail=detail,
        ))

    logger.info("wscn fetched %d hot articles", len(items))
    return items
