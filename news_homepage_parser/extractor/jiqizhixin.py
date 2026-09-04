"""
机器之心文章库提取器

通过官方内部 API 获取最新文章列表，无需 Playwright。
API: https://www.jiqizhixin.com/api/article_library/articles.json?page=1&per=15

返回字段示例：
{
  "id": "247f757d-...",
  "title": "苹果新作：内化视觉思考，推理提速 5 倍",
  "slug": "2026-09-03-7",
  "category": "practice",
  "tagList": ["IVT", "Apple"],
  "author": "机器之心",
  "publishedAt": "2026/09/03 15:06",
  "content": "摘要...",
  "source": "机器之心"
}
"""
import json
import logging
import urllib.request
import urllib.error

from news_homepage_parser.models import NewsItem

logger = logging.getLogger(__name__)

_API_URL = "https://www.jiqizhixin.com/api/article_library/articles.json"
_BASE_URL = "https://www.jiqizhixin.com"

# category 值 → 友好 section 名（用于 section 字段）
_CATEGORY_MAP = {
    "practice":   "practice",
    "research":   "research",
    "industry":   "industry",
    "technology": "technology",
    "news":       "news",
}


def fetch_articles(page_size: int = 15) -> list[NewsItem]:
    """
    调用机器之心文章库 API，返回最新文章列表。
    section = article.category（原始值），rank = 列表顺序。
    """
    url = f"{_API_URL}?page=1&per={page_size}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.jiqizhixin.com/articles",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.error("jiqizhixin api http error: %s", e)
        return []
    except Exception as e:
        logger.error("jiqizhixin api error: %s", e)
        return []

    if not data.get("success"):
        logger.warning("jiqizhixin api success=false: %s", str(data)[:200])
        return []

    items: list[NewsItem] = []
    for rank, article in enumerate(data.get("articles", []), start=1):
        title = (article.get("title") or "").strip()
        slug = (article.get("slug") or "").strip()
        if not title or not slug:
            continue

        link = f"{_BASE_URL}/articles/{slug}"
        category = article.get("category") or ""
        section = _CATEGORY_MAP.get(category, category) or "section_1"

        # 把标签和发布时间存入 detail
        tag_list = article.get("tagList") or []
        published_at = article.get("publishedAt") or ""
        detail = {}
        if tag_list:
            detail["tags"] = tag_list
        if published_at:
            detail["published_at"] = published_at

        items.append(NewsItem(
            title=title,
            link=link,
            section=section,
            rank=rank,
            ranktime="",
            detail=detail if detail else None,
        ))

    logger.info("jiqizhixin fetched %d articles", len(items))
    return items
