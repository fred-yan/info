from bs4 import BeautifulSoup
from news_homepage_parser.models import NewsItem
from ._utils import resolve_link


def extract(html_or_soup, base_url: str) -> list[NewsItem]:
    """
    WSJ 中文专用策略：
    - 如果是字符串且包含 TAB_SEPARATOR，则处理多次抓取（今日+本周）
    - 否则只提取首页第一个栏目的文章（前10篇）
    """
    import logging
    from ._utils import dedup
    logger = logging.getLogger(__name__)
    
    items = []
    
    # 检查是否是多次抓取
    if isinstance(html_or_soup, str) and "<!-- TAB_SEPARATOR -->" in html_or_soup:
        parts = html_or_soup.split("<!-- TAB_SEPARATOR -->")
        logger.debug(f"WSJ multi-fetch: {len(parts)} parts")
        
        # 第一部分：首页 + 热门文章-今日
        soup1 = BeautifulSoup(parts[0], "html.parser")
        first_section = _extract_first_section(soup1, base_url)
        hot_today = _extract_hot_articles(soup1, base_url, "today")
        
        # 单独去重每个部分
        first_section = dedup(first_section)
        hot_today = dedup(hot_today)
        
        logger.debug(f"WSJ part1: first_section={len(first_section)}, hot_today={len(hot_today)}")
        items.extend(first_section)
        items.extend(hot_today)
        
        # 第二部分：热门文章-本周
        if len(parts) > 1:
            soup2 = BeautifulSoup(parts[1], "html.parser")
            hot_week = _extract_hot_articles(soup2, base_url, "week")
            
            # 单独去重
            hot_week = dedup(hot_week)
            
            logger.debug(f"WSJ part2: hot_week={len(hot_week)}")
            items.extend(hot_week)
    else:
        # 单次抓取
        soup = html_or_soup if isinstance(html_or_soup, BeautifulSoup) else BeautifulSoup(html_or_soup, "html.parser")
        first_section = _extract_first_section(soup, base_url)
        hot_today = _extract_hot_articles(soup, base_url, "today")
        
        # 单独去重每个部分
        first_section = dedup(first_section)
        hot_today = dedup(hot_today)
        
        items.extend(first_section)
        items.extend(hot_today)
    
    return items


def _extract_first_section(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """提取首页第一个栏目的文章（前10篇），section 命名为 section_1。"""
    items = []
    seen: set[str] = set()

    # 提取前10个标题标签的文章（h1/h2/h3 都可能包含头条）
    count = 0
    for heading in soup.find_all(["h1", "h2", "h3"]):
        if count >= 10:
            break
        
        a = heading.find("a", href=True)
        if not a:
            # 检查标题的父元素是否是 a 标签
            if heading.parent.name == "a" and heading.parent.get("href"):
                a = heading.parent
        
        if not a:
            continue
        
        href = a.get("href", "")
        if not href:
            continue
        # 接受 /articles/ 和 /story/ 路径的文章链接
        if "/articles/" not in href and "/story/" not in href:
            continue
        
        link = resolve_link(href, base_url)
        if link in seen:
            continue
        
        seen.add(link)
        title = heading.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        
        items.append(NewsItem(title=title, link=link, section="section_1"))
        count += 1

    return items


def _extract_hot_articles(soup: BeautifulSoup, base_url: str, section_type: str) -> list[NewsItem]:
    """
    提取热门文章列表。
    section_type: "today" 或 "week"
    - today: section="hotlist", ranktime="24hour"
    - week: section="hotlist", ranktime="168hour"
    """
    import logging
    logger = logging.getLogger(__name__)
    
    items = []
    
    # 根据 section_type 设置 section 和 ranktime
    if section_type == "today":
        section_name = "hotlist"
        ranktime = "24hour"
        search_text = "热门文章-今日"
    else:  # week
        section_name = "hotlist"
        ranktime = "168hour"
        search_text = "热门文章-本周"
    
    # 查找"热门文章"标题
    h4 = soup.find('h4', string=lambda s: s and '热门文章' in s if s else False)
    if not h4:
        logger.debug(f"WSJ {search_text}: h4 not found")
        return items
    
    logger.debug(f"WSJ {search_text}: h4 found")
    
    # 向上找到容器
    hot_container = h4.parent
    if not hot_container:
        logger.debug(f"WSJ {search_text}: container not found")
        return items
    
    logger.debug(f"WSJ {search_text}: container found")
    
    # 查找 ul 列表
    ul = hot_container.find('ul')
    if not ul:
        logger.debug(f"WSJ {search_text}: ul not found")
        return items
    
    logger.debug(f"WSJ {search_text}: ul found")
    
    # 提取文章
    for rank, li in enumerate(ul.find_all('li'), 1):
        a = li.find('a', href=True)
        if not a:
            continue
        
        href = a['href']
        if '/articles/' not in href:
            continue
        
        title = a.get_text(strip=True)
        if len(title) < 5:
            continue
        
        link = resolve_link(href, base_url)
        if title and link:
            items.append(NewsItem(
                title=title, 
                link=link, 
                section=section_name, 
                rank=rank,
                ranktime=ranktime
            ))
    
    logger.debug(f"WSJ {search_text}: extracted {len(items)} items")
    return items
