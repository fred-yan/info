"""
MIT Technology Review Most Popular 提取器

数据内嵌于 SSR HTML 的 Next.js/Irving JSON blob 中：
  {"name":"acf/gallery-section","config":{"title":"Most Popular","posts":[
    {"name":"homepage-story-card","config":{"hed":"文章标题","link":"https://..."}},
    ...
  ]}}

用正则从 HTML 中提取该 JSON 片段。
"""
import json
import logging
import re
from bs4 import BeautifulSoup
from news_homepage_parser.models import NewsItem
from ._utils import resolve_link

logger = logging.getLogger(__name__)

# 匹配 "Most Popular" posts 数组的正则（贪婪匹配，括号平衡）
_PATTERN = re.compile(
    r'"title"\s*:\s*"Most Popular"[^}]*?"posts"\s*:\s*(\[)',
    re.DOTALL,
)


def _extract_json_array(html: str, start_pos: int) -> list:
    """
    从 start_pos（'[' 位置）开始，平衡括号提取完整 JSON 数组。
    """
    depth = 0
    for i in range(start_pos, len(html)):
        if html[i] == "[":
            depth += 1
        elif html[i] == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start_pos : i + 1])
                except json.JSONDecodeError:
                    return []
    return []


def extract(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """
    提取 Most Popular 列表。
    section="hotlist", rank=列表顺序, ranktime=""
    """
    items: list[NewsItem] = []
    html = str(soup)

    match = _PATTERN.search(html)
    if not match:
        logger.warning("mittr: Most Popular JSON blob not found")
        return items

    bracket_pos = match.end() - 1  # 指向 '[' 字符
    posts = _extract_json_array(html, bracket_pos)
    if not posts:
        logger.warning("mittr: could not parse Most Popular posts array")
        return items

    seen: set[str] = set()
    for rank, post in enumerate(posts, start=1):
        cfg = post.get("config", {})
        title = (cfg.get("hed") or cfg.get("title") or "").strip()
        link_raw = (cfg.get("link") or cfg.get("url") or cfg.get("href") or "").strip()
        if not title or not link_raw:
            continue
        link = resolve_link(link_raw, base_url)
        if link in seen:
            continue
        seen.add(link)
        items.append(NewsItem(
            title=title,
            link=link,
            section="hotlist",
            rank=rank,
            ranktime="",
        ))

    logger.info("mittr extracted %d articles", len(items))
    return items
