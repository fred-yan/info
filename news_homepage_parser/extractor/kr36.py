from bs4 import BeautifulSoup
from news_homepage_parser.models import NewsItem
from ._utils import resolve_link

_SECTION_MAP = {
    "人气榜": "renqi",
    "综合榜": "zonghe",
    "收藏榜": "shoucang",
}


def extract(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """
    36氪热榜专用策略：提取人气榜、综合榜、收藏榜三个榜单（不去重，带排名）。
    所有 section 命名为 hotlist，通过 attr 字段区分榜单类型。
    """
    items = []

    for wrapper in soup.find_all("div", class_="list-section-wrapper"):
        attr_value = None
        for keyword, slug in _SECTION_MAP.items():
            if wrapper.find(string=lambda t: t and keyword in t):
                attr_value = slug
                break

        # 提取文章并添加排名
        rank = 0
        for a in wrapper.find_all("a", class_="article-item-title", href=True):
            href = a["href"]
            if "/p/" not in href:
                continue
            link = resolve_link(href, base_url)
            title = a.get_text(strip=True)
            if not title:
                continue
            
            rank += 1
            
            # 创建 detail 字典，包含 attr
            detail = {"attr": attr_value} if attr_value else None
            
            items.append(NewsItem(
                title=title, 
                link=link, 
                section="hotlist",  # 统一命名为 hotlist
                rank=rank,
                attr=attr_value,  # 添加 attr 字段
                ranktime="48hour",  # 添加 ranktime 字段
                detail=detail  # 添加 detail 字段
            ))

    return items
