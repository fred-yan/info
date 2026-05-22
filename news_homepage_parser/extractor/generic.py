from bs4 import BeautifulSoup
from news_homepage_parser.models import NewsItem
from ._utils import resolve_link, find_section


def extract(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """通用策略：查找 <article> 或 <h2> 标签提取新闻条目。"""
    items = []
    articles = soup.find_all("article")

    if articles:
        for article in articles:
            heading = article.find(["h2", "h3"])
            if not heading:
                continue
            title = heading.get_text(strip=True)
            if not title:
                continue
            a_tag = article.find("a", href=True)
            if not a_tag:
                continue
            link = resolve_link(a_tag["href"], base_url)
            if not link:
                continue
            section = find_section(article, soup)
            items.append(NewsItem(title=title, link=link, section=section))
    else:
        for h2 in soup.find_all("h2"):
            title = h2.get_text(strip=True)
            if not title:
                continue
            a_tag = h2.find("a", href=True)
            if not a_tag:
                sibling = h2.find_next_sibling()
                if sibling:
                    a_tag = sibling.find("a", href=True) if sibling.name != "a" else sibling
                    if not a_tag and sibling.name == "a" and sibling.get("href"):
                        a_tag = sibling
            if not a_tag:
                continue
            link = resolve_link(a_tag["href"], base_url)
            if not link:
                continue
            section = find_section(h2, soup)
            items.append(NewsItem(title=title, link=link, section=section))

    return items
