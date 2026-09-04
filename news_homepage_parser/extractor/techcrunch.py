"""
TechCrunch Most Popular 提取器

HTML 结构（Playwright 渲染后）：
  <div class="... wp-block-techcrunch-most-popular-posts ...">
    <ul class="wp-block-post-template">
      <li class="wp-block-post ...">
        <a class="loop-card__title-link" href="https://techcrunch.com/...">标题</a>
      </li>
    </ul>
  </div>
"""
import logging
from bs4 import BeautifulSoup
from news_homepage_parser.models import NewsItem
from ._utils import resolve_link

logger = logging.getLogger(__name__)


def extract(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """
    提取 Most Popular 列表。
    section="hotlist", rank=列表顺序, ranktime=""
    """
    items: list[NewsItem] = []

    # 定位 Most Popular 容器
    container = soup.find(
        lambda t: t.name == "div"
        and t.get("class")
        and any("most-popular" in c for c in t.get("class", []))
    )
    if not container:
        # 备用：找标题文字为 "Most Popular" 的块
        heading = soup.find(
            lambda t: t.name in ("h2", "h3", "h4", "p", "span")
            and t.get_text(strip=True) == "Most Popular"
        )
        if heading:
            container = heading.find_parent(["div", "section", "aside"])

    if not container:
        logger.warning("techcrunch: Most Popular container not found")
        return items

    seen: set[str] = set()
    rank = 0
    for li in container.find_all("li"):
        # 尝试找带 loop-card__title-link 的链接，备用直接找 a
        a = li.find("a", class_=lambda c: c and "title-link" in c)
        if not a:
            a = li.find("a", href=True)
        if not a:
            continue
        href = a.get("href", "")
        title = a.get_text(strip=True)
        if not title or not href:
            continue
        link = resolve_link(href, base_url)
        if link in seen:
            continue
        seen.add(link)
        rank += 1
        items.append(NewsItem(
            title=title,
            link=link,
            section="hotlist",
            rank=rank,
            ranktime="",
        ))

    logger.info("techcrunch extracted %d articles", len(items))
    return items
