from bs4 import BeautifulSoup
from news_homepage_parser.models import NewsItem
from ._utils import resolve_link


# ── API-based fetcher (no Playwright needed) ──────────────────────────────────

def fetch_article_list(page_size: int = 20) -> list[NewsItem]:
    """
    通过 api-article.huxiu.com 接口获取虎嗅文章列表，无需 Playwright。
    虎嗅首页部署了阿里云 WAF 滑动验证码，Playwright 无法绕过，改用内部 API。
    返回 section="section_1" 的 NewsItem 列表。
    """
    import logging
    import urllib.request
    import urllib.error
    import json

    logger = logging.getLogger(__name__)
    url = f"https://api-article.huxiu.com/web/article/articleList?platform=www&pagesize={page_size}"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.huxiu.com/",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.huxiu.com",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.error("huxiu api http error: %s", e)
        return []
    except Exception as e:
        logger.error("huxiu api error: %s", e)
        return []

    if not data.get("success"):
        logger.warning("huxiu api returned success=false: %s", data)
        return []

    items = []
    for rank, article in enumerate(data.get("data", {}).get("dataList", []), 1):
        title = article.get("title", "").strip()
        aid = article.get("aid", "")
        share_url = article.get("share_url", "")

        if not title or not aid:
            continue

        link = share_url or f"https://www.huxiu.com/article/{aid}.html"
        link = link.replace("m.huxiu.com", "www.huxiu.com")

        is_original = article.get("is_original", "0") == "1"
        detail = {"attr": "original"} if is_original else None

        items.append(NewsItem(
            title=title,
            link=link,
            section="section_1",
            rank=rank,
            detail=detail,
        ))

    logger.info("huxiu api fetched %d articles", len(items))
    return items
