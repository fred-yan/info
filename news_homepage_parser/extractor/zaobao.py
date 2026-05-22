"""早报（zaobao.com.sg/cn）新闻提取器。

提取首页头条新闻、各分类新闻和热门文章。
"""
import logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from news_homepage_parser.models import NewsItem
from ._utils import resolve_link

logger = logging.getLogger(__name__)

# 首页新闻栏目 ref 标识 → section 名称
_SECTION_MAP = {
    'home-top-news': 'section_1',
    'home-china-news': 'section_2',
    'home-global-news': 'section_3',
}

BASE_URL = "https://www.zaobao.com.sg"


def _extract_title(a_tag) -> str:
    """从 <a> 标签中提取标题。优先 title 属性，其次文本内容。"""
    title = a_tag.get('title', '').strip()
    if not title:
        title = a_tag.get_text(strip=True)
    return title


def _extract_articles_by_ref(soup: BeautifulSoup, ref_key: str, section: str) -> list[NewsItem]:
    """按 ref 标识提取文章列表，自动去重（同一 href 只取一次）。"""
    items: list[NewsItem] = []
    seen_hrefs: set[str] = set()

    links = soup.find_all('a', href=lambda h: h and f'ref={ref_key}' in h)

    rank = 0
    for a in links:
        href = a.get('href', '')
        if not href or '/story' not in href:
            continue

        # 去掉 ref 参数，得到干净的路径
        clean_href = href.split('?')[0]
        if clean_href in seen_hrefs:
            continue

        title = _extract_title(a)
        if not title or len(title) < 4:
            continue

        seen_hrefs.add(clean_href)
        rank += 1

        link = clean_href if clean_href.startswith('http') else BASE_URL + clean_href
        items.append(NewsItem(title=title, link=link, section=section, rank=rank))

    return items


def extract(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """提取早报首页各栏目的新闻文章。

    提取头条(section_1)、新加坡(section_2)、中国(section_3)、国际(section_4)。
    """
    items: list[NewsItem] = []

    for ref_key, section in _SECTION_MAP.items():
        section_items = _extract_articles_by_ref(soup, ref_key, section)
        items.extend(section_items)

    logger.debug("zaobao extract items=%d", len(items))
    return items


def extract_finance(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """提取每日热门文章（home-popular-day），作为 hotlist。"""
    items: list[NewsItem] = []
    seen_hrefs: set[str] = set()

    popular_links = soup.find_all(
        'a', href=lambda h: h and 'ref=home-popular-day' in h
    )

    rank = 0
    for a in popular_links:
        href = a.get('href', '')
        if not href or '/story' not in href:
            continue

        clean_href = href.split('?')[0]
        if clean_href in seen_hrefs:
            continue

        title = _extract_title(a)
        if not title or len(title) < 4:
            continue

        seen_hrefs.add(clean_href)
        rank += 1

        link = clean_href if clean_href.startswith('http') else BASE_URL + clean_href
        items.append(NewsItem(
            title=title,
            link=link,
            section='hotlist',
            rank=rank,
            ranktime='24hour',
        ))

    logger.debug("zaobao popular/hotlist items=%d", len(items))
    return items


# ---------- 热门榜单（独立抓取） ----------

_RANKTIME_MAP = {
    "day": "24hour",
    "week": "168hour",
}

_REF_MAP = {
    "day": "home-popular-day",
    "week": "home-popular-week",
}


def fetch_hotlist(since: str = "day") -> tuple[bool, list[NewsItem] | str]:
    """
    抓取并解析早报热门榜单。
    since: "day" | "week"
    返回 (True, items) 或 (False, error_message)
    """
    from news_homepage_parser.fetcher import fetch

    if since not in _RANKTIME_MAP:
        return (False, f"Invalid since value: {since!r}. Must be 'day' or 'week'")

    ok, html_or_err = fetch("https://www.zaobao.com.sg/cn")
    if not ok:
        return (False, html_or_err)

    items = _parse_hotlist(html_or_err, since)
    logger.debug("zaobao hotlist since=%s items=%d", since, len(items))
    return (True, items)


def fetch_hotlist_all() -> tuple[bool, dict[str, list[NewsItem]] | str]:
    """
    一次抓取，同时返回日榜和周榜。
    返回 (True, {"day": [...], "week": [...]}) 或 (False, error_message)
    """
    from news_homepage_parser.fetcher import fetch

    ok, html_or_err = fetch("https://www.zaobao.com.sg/cn")
    if not ok:
        return (False, html_or_err)

    day_items = _parse_hotlist(html_or_err, "day")
    week_items = _parse_hotlist(html_or_err, "week")
    logger.debug("zaobao hotlist_all day=%d week=%d", len(day_items), len(week_items))
    return (True, {"day": day_items, "week": week_items})


def _parse_hotlist(html: str, since: str) -> list[NewsItem]:
    """从首页 HTML 中解析热门文章列表。"""
    soup = BeautifulSoup(html, "html.parser")
    ranktime = _RANKTIME_MAP[since]
    ref_key = _REF_MAP[since]
    items: list[NewsItem] = []
    seen_hrefs: set[str] = set()

    popular_links = soup.find_all(
        'a', href=lambda h: h and f'ref={ref_key}' in h
    )

    rank = 0
    for a in popular_links:
        href = a.get('href', '')
        if not href or '/story' not in href:
            continue

        clean_href = href.split('?')[0]
        if clean_href in seen_hrefs:
            continue

        title = _extract_title(a)
        if not title or len(title) < 4:
            continue

        seen_hrefs.add(clean_href)
        rank += 1

        url = clean_href if clean_href.startswith('http') else BASE_URL + clean_href

        items.append(NewsItem(
            title=title,
            link=url,
            section='hotlist',
            rank=rank,
            ranktime=ranktime,
            detail={'desc': title},
        ))

    return items
