"""
Washington Post 提取器：提取首页前 3 个栏目的文章和 Most Read 栏目
"""
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import logging
from news_homepage_parser.models import NewsItem
from ._utils import resolve_link, section_from_path

logger = logging.getLogger(__name__)


def extract(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """提取 Washington Post 首页前 3 个栏目的文章。"""
    items = []
    seen_titles: set[str] = set()
    
    # 查找主内容区域
    main_content = soup.find("main") or soup.find("div", id="main-content") or soup.body
    
    if not main_content:
        logger.debug("washingtonpost main content not found")
        return items
    
    # 提取前 3 个栏目的文章（通过 h2 标题）
    section_count = 0
    articles_per_section = []
    current_section_articles = []
    
    for h2 in main_content.find_all("h2"):
        title = h2.get_text(strip=True)
        if not title or len(title) < 15:
            continue
        
        # 跳过重复标题
        if title in seen_titles:
            continue
        
        # 查找链接
        a_tag = h2.find("a", href=True)
        if not a_tag:
            # 查找父元素中的链接
            for parent in h2.parents:
                a_tag = parent.find("a", href=True)
                if a_tag:
                    break
                if parent == main_content:
                    break
        
        if not a_tag or not a_tag.get("href"):
            continue
        
        href = a_tag["href"]
        
        # 只保留文章链接（包含年份）
        if not any(year in href for year in ["/2026/", "/2025/", "/2024/"]):
            continue
        
        # 跳过特殊链接
        if any(skip in href for skip in ("/search", "/login", "/subscribe", "#", "javascript:")):
            continue
        
        link = resolve_link(href, base_url)
        section = section_from_path(urlparse(href).path)
        seen_titles.add(title)
        current_section_articles.append(NewsItem(title=title, link=link, section=f"section_{section_count + 1}"))
        
        # 每个栏目收集一定数量的文章后切换到下一个栏目
        # 简单策略：每 3-5 篇文章算一个栏目
        if len(current_section_articles) >= 3:
            articles_per_section.append(current_section_articles)
            current_section_articles = []
            section_count += 1
            
            # 只提取前 3 个栏目
            if section_count >= 3:
                break
    
    # 添加最后一个栏目的文章（如果有）
    if current_section_articles and section_count < 3:
        articles_per_section.append(current_section_articles)
    
    # 合并所有栏目的文章
    for section_articles in articles_per_section:
        items.extend(section_articles)
    
    logger.debug("washingtonpost extract items=%d from %d sections", len(items), len(articles_per_section))
    return items


def extract_most_read(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """提取 'Most Read' 区块（带 rank 和 ranktime）。"""
    items = []
    
    # 查找包含 data-rte-module-category="most-read" 的容器
    most_read_container = soup.find("div", attrs={"data-rte-module-category": "most-read"})
    
    if not most_read_container:
        logger.debug("washingtonpost most_read container not found")
        return []
    
    logger.debug("washingtonpost found most_read container")
    
    seen_titles: set[str] = set()
    
    # 查找所有包含 data-feature-name="most-read" 的卡片
    cards = most_read_container.find_all("div", attrs={"data-feature-name": "most-read"})
    
    logger.debug("washingtonpost found %d most_read cards", len(cards))
    
    for card in cards:
        # 查找排名数字（在 card-sidebar 中）
        sidebar = card.find("div", class_="card-sidebar")
        if not sidebar:
            continue
        
        rank_elem = sidebar.find("div", class_=lambda x: x and "PJLV" in x)
        if not rank_elem:
            continue
        
        try:
            rank = int(rank_elem.get_text(strip=True))
        except ValueError:
            continue
        
        # 查找标题和链接
        h2 = card.find("h2")
        if not h2:
            continue
        
        a_tag = h2.find("a", href=True)
        if not a_tag:
            continue
        
        href = a_tag.get("href", "")
        title = a_tag.get_text(strip=True)
        
        # 过滤
        if not title or len(title) < 15 or title in seen_titles:
            continue
        
        link = resolve_link(href, base_url)
        seen_titles.add(title)
        items.append(NewsItem(
            title=title,
            link=link,
            section="hotlist",
            rank=rank,
            ranktime="48hour"
        ))
    
    # 按 rank 排序
    items.sort(key=lambda x: x.rank if x.rank else 999)
    
    logger.debug("washingtonpost most_read items=%d", len(items))
    return items
