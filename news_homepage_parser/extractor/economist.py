"""
Economist 提取器（新版 HTML 结构）：
- 指定分类区块：Business, Finance & economics, United States, Artificial intelligence
- Stories most read by subscribers（前 5 篇）
"""
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import logging
from news_homepage_parser.models import NewsItem
from ._utils import resolve_link, section_from_path

logger = logging.getLogger(__name__)

# 目标分类（通过 /topics/ 链接匹配）- 移除 Podcasts
_TARGET_TOPICS = {
    "/topics/business": "Business",
    "/topics/finance-and-economics": "Finance & Economics",
    "/topics/united-states": "United States",
    "/topics/artificial-intelligence": "Artificial Intelligence",
}


def extract(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """
    提取 Economist 首页文章：
    1. 从首页顶部提取第 1、2、3 栏的文章（带 desc 字段）
    2. 从指定的 /topics/ 分类区块中提取文章（Business, Finance & Economics, United States, AI）
    """
    items: list[NewsItem] = []

    def add_item(title: str, href: str, section: str | None, desc: str | None = None):
        if not title or title.lower() in ("undefined undefined", ""):
            return
        if any(skip in href for skip in ("/subscribe", "/login", "#", "javascript:")):
            return
        link = resolve_link(href, base_url)
        # 去掉 query string
        link_key = link.split("?")[0]
        # 如果有 desc，放入 detail 字典
        detail = {"desc": desc} if desc else None
        items.append(NewsItem(title=title, link=link_key, section=section, detail=detail))

    # === 新增：提取首页顶部第 1、2、3 栏文章（带 desc） ===
    # 查找父容器 div.e17npd3y1（包含 css-0 类）
    top_containers = soup.find_all("div", class_="e17npd3y1")
    
    for top_container in top_containers:
        # 查找所有直接子元素 div.e17npd3y0（包含 css-z3oexc 类）
        article_containers = top_container.find_all("div", class_="e17npd3y0", recursive=False)
        
        if len(article_containers) >= 3:
            # 提取前 3 个容器中的文章
            for idx, container in enumerate(article_containers[:3], start=1):
                section_name = f"section_{idx}"
                
                # 查找标题和链接 - 使用 class 包含 "headline" 的 h3
                headline_elem = container.find("h3", class_=lambda x: x and "headline" in x)
                if not headline_elem:
                    continue
                
                a = headline_elem.find("a", href=True)
                if not a:
                    continue
                
                title = a.get_text(strip=True)
                href = a["href"]
                
                # 查找 rubric（描述文本）
                rubric_elem = container.find("p", class_=lambda x: x and "rubric" in x)
                desc = rubric_elem.get_text(strip=True) if rubric_elem else None
                
                add_item(title, href, section_name, desc)
            
            # 找到第一个有效的容器后就退出
            break

    # === 保留原有：提取 Business 等 4 个栏目 ===
    # 找所有 h3 中包含 /topics/ 链接的分类标题
    for h3 in soup.find_all("h3"):
        a = h3.find("a", href=True)
        if not a:
            continue
        
        href = a["href"]
        section_label = _TARGET_TOPICS.get(href)
        if not section_label:
            continue
        
        # 找这个 h3 的父容器，然后找其中的 ul 列表
        for parent in h3.parents:
            ul = parent.find("ul")
            if ul:
                # 提取 ul 中的所有文章
                for li in ul.find_all("li"):
                    article_h3 = li.find("h3")
                    if not article_h3:
                        continue
                    title = article_h3.get_text(strip=True)
                    article_a = article_h3.find("a", href=True)
                    if article_a:
                        add_item(title, article_a["href"], section_label)
                break
            if parent.name in ("main", "body"):
                break

    logger.debug("economist extract items=%d", len(items))
    return items


def extract_most_read(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """
    提取 'Stories most read by subscribers' 区块，最多 5 篇。
    添加 rank 字段表示排名，section 命名为 hotlist，ranktime 为 48hour。
    """
    # 找包含 "Stories most read by subscribers" 的 h2
    target_h2 = None
    for h2 in soup.find_all("h2"):
        text = h2.get_text(strip=True).lower()
        if "most read" in text and "subscribers" in text:
            target_h2 = h2
            break
    
    if not target_h2:
        logger.debug("economist most_read section not found")
        return []

    # 找 h2 所在的 section
    section = None
    for parent in target_h2.parents:
        if parent.name == "section":
            section = parent
            break
        if parent.name in ("main", "body"):
            break
    
    if not section:
        logger.debug("economist most_read section container not found")
        return []

    # 在 section 中找 ol 或 ul 列表
    items = []
    for list_elem in section.find_all(["ol", "ul"]):
        lis = list_elem.find_all("li")
        if len(lis) >= 5:
            # 提取前 5 个，添加 rank 和 ranktime
            for rank, li in enumerate(lis[:5], start=1):
                h3 = li.find("h3")
                if not h3:
                    continue
                title = h3.get_text(strip=True)
                a = h3.find("a", href=True)
                if not a:
                    continue
                href = a["href"]
                # 去掉 query string
                link = resolve_link(href, base_url).split("?")[0]
                items.append(NewsItem(
                    title=title, 
                    link=link, 
                    section="hotlist",
                    rank=rank,
                    ranktime="48hour"
                ))
            break
    
    logger.debug("economist most_read items=%d", len(items))
    return items
