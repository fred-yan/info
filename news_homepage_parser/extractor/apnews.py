from urllib.parse import urlparse
from bs4 import BeautifulSoup
from news_homepage_parser.models import NewsItem
from ._utils import resolve_link, find_direct_heading
import logging

logger = logging.getLogger(__name__)


def _extract_promos_from_container(container, section_name: str, seen_titles: set) -> list[NewsItem]:
    """从一个 PageListStandardE 容器中提取所有文章。"""
    items = []

    # 提取 lead promo（主要文章）
    lead_promo = container.find('div', class_='PageListStandardE-leadPromo-info')
    if lead_promo:
        promo_title = lead_promo.find(class_='PagePromo-title')
        if promo_title:
            a = promo_title.find('a', href=True)
            if a:
                title_span = a.find('span', class_='PagePromoContentIcons-text')
                title = title_span.get_text(strip=True) if title_span else a.get_text(strip=True)
                href = a['href']

                if title and len(title) >= 10 and title not in seen_titles:
                    link = resolve_link(href, 'https://apnews.com')
                    if link:
                        items.append(NewsItem(title=title, link=link, section=section_name))
                        seen_titles.add(title)

    # 提取 secondary articles
    secondary_section = container.find('div', class_='PageListStandardE-items-secondary')
    if secondary_section:
        promos = secondary_section.find_all('div', class_='PagePromo')
        for promo in promos:
            promo_title = promo.find(class_='PagePromo-title')
            if promo_title:
                a = promo_title.find('a', href=True)
                if a:
                    title_span = a.find('span', class_='PagePromoContentIcons-text')
                    title = title_span.get_text(strip=True) if title_span else a.get_text(strip=True)
                    href = a['href']

                    if title and len(title) >= 10 and title not in seen_titles:
                        link = resolve_link(href, 'https://apnews.com')
                        if link:
                            items.append(NewsItem(title=title, link=link, section=section_name))
                            seen_titles.add(title)

    # 如果没有 lead/secondary 结构，直接提取所有 PagePromo-title
    if not lead_promo and not secondary_section:
        for promo_title in container.find_all(class_='PagePromo-title'):
            a = promo_title.find('a', href=True)
            if a:
                title_span = a.find('span', class_='PagePromoContentIcons-text')
                title = title_span.get_text(strip=True) if title_span else a.get_text(strip=True)
                href = a['href']

                if title and len(title) >= 10 and title not in seen_titles:
                    link = resolve_link(href, 'https://apnews.com')
                    if link:
                        items.append(NewsItem(title=title, link=link, section=section_name))
                        seen_titles.add(title)

    return items


def extract(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """
    AP News 专用策略：提取首页主要区域的文章。
    从 PageListStandardE 容器中提取各区域文章。
    """
    items = []
    seen_titles: set[str] = set()

    # 区域映射：命名区域 → section 名称
    # AP News 会不定期更换区域名称（如 A1 → Election main），
    # 所以我们按顺序处理所有 PageListStandardE 容器
    containers = soup.find_all('div', class_='PageListStandardE', attrs={'data-gtm-region': True})

    section_index = 1
    for container in containers:
        region = container.get('data-gtm-region', '')

        # 跳过无意义的区域（如纯选举结果页面链接）
        promos = container.find_all(class_='PagePromo-title')
        if len(promos) < 2 and region == '':
            continue

        section_name = f'section_{section_index}'
        section_items = _extract_promos_from_container(container, section_name, seen_titles)

        if section_items:
            items.extend(section_items)
            section_index += 1

    logger.debug("apnews extract items=%d from %d sections", len(items), section_index - 1)
    return items


def extract_most_read(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """
    提取 AP News 的 Most Read 栏目文章。
    Most Read 区块位于 <h2 class="PageList-header-title">Most read</h2> 标题下。
    添加 rank 字段表示排名，section 命名为 hotlist，ranktime 为 48hour。
    """
    import re
    items = []

    # 找 Most Read 标题
    h2 = soup.find('h2', class_='PageList-header-title', string=re.compile(r'most\s+read', re.I))
    if not h2:
        return items

    # 向上找到 PageListRightRailA 容器
    container = h2.find_parent('div', class_='PageListRightRailA')
    if not container:
        return items

    # 提取文章链接，添加排名和 ranktime
    seen_titles: set[str] = set()
    rank = 1
    for promo_title in container.find_all(class_='PagePromo-title'):
        a = promo_title.find('a', href=True)
        if not a:
            continue

        title_span = a.find('span', class_='PagePromoContentIcons-text')
        title = title_span.get_text(strip=True) if title_span else a.get_text(strip=True)
        href = a['href']

        if not title or len(title) < 10 or title in seen_titles:
            continue

        link = resolve_link(href, base_url)
        if link:
            seen_titles.add(title)
            items.append(NewsItem(title=title, link=link, section='hotlist', rank=rank, ranktime='48hour'))
            rank += 1

    return items
