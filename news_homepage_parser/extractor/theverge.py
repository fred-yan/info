"""
The Verge Most Popular 提取器

HTML 结构（Playwright 渲染后）：
  <section class="... duet--homepage--most-popular">
    <ol class="...">
      <li class="...">
        <a href="https://www.theverge.com/...">文章标题</a>
      </li>
    </ol>
  </section>
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

    # 定位 Most Popular section
    section = soup.find("section", class_=lambda c: c and "most-popular" in c)
    if not section:
        # 备用：找包含 "Most Popular" 文字的 section/div
        section = soup.find(
            lambda t: t.name in ("section", "div", "aside")
            and t.get_text(separator=" ").strip().startswith("Most Popular")
        )
    if not section:
        logger.warning("theverge: Most Popular section not found")
        return items

    ol = section.find("ol")
    if not ol:
        logger.warning("theverge: ol not found in Most Popular section")
        return items

    seen: set[str] = set()
    for rank, li in enumerate(ol.find_all("li", recursive=False), start=1):
        a = li.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or not href:
            continue
        link = resolve_link(href, base_url)
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

    logger.info("theverge extracted %d articles", len(items))
    return items
