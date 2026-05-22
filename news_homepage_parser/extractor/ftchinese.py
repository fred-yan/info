from bs4 import BeautifulSoup
from news_homepage_parser.models import NewsItem
from ._utils import resolve_link


def extract(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """
    FT 中文网专用策略：提取首页第一栏文章（头条区域）。
    从 div.item-container 中提取 a.item-headline-link 的文章链接。
    只取前 10 篇作为首页第一栏内容。
    """
    items = []
    seen_links: set[str] = set()

    for item_container in soup.find_all('div', class_='item-container'):
        a = item_container.find('a', class_='item-headline-link')
        if not a:
            continue

        href = a.get('href', '')
        if not href:
            continue
        # 只保留文章链接
        if not ('/story/' in href or '/premium/' in href or '/interactive/' in href):
            continue

        title = a.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        link = resolve_link(href, base_url)
        if link in seen_links:
            continue
        seen_links.add(link)

        items.append(NewsItem(title=title, link=link, section='section_1'))

        # 只取前 10 篇
        if len(items) >= 10:
            break

    return items


def extract_hot_articles(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """
    提取"热门文章"栏目，section 命名为 hotlist，包含排名和 ranktime。
    """
    items = []
    
    # 查找"热门文章"标题
    h2 = soup.find('h2', class_='list-title', string=lambda s: '热门文章' in s if s else False)
    if not h2:
        return items
    
    # 向上找到 mps 容器
    mps_div = h2.find_parent('div', class_='mps')
    if not mps_div:
        return items
    
    # 在 mps 中找 ul.top10
    ul = mps_div.find('ul', class_='top10')
    if not ul:
        return items
    
    # 提取文章链接，保留排名和关键词
    for li in ul.find_all('li'):
        a = li.find('a', href=True)
        if not a:
            continue
        
        href = a['href']
        title = a.get_text(strip=True)
        
        if len(title) < 10:
            continue
        
        # 提取排名（从 li 的 class 中，如 mp1, mp2, ...）
        rank = None
        li_classes = li.get('class', [])
        for cls in li_classes:
            if cls.startswith('mp') and len(cls) > 2:
                try:
                    rank = int(cls[2:])
                    break
                except ValueError:
                    pass
        
        # 提取 keywords
        keywords = li.get('data-keywords', '')
        
        link = resolve_link(href, base_url)
        if title and link:
            # 将 keywords 放入 detail 字典
            detail = {"keywords": keywords} if keywords else None
            items.append(NewsItem(
                title=title, 
                link=link, 
                section='hotlist',
                rank=rank, 
                ranktime='48hour',
                detail=detail
            ))
    
    return items


def extract_hot_premium(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """
    提取"热门付费文章"栏目，section 命名为 hotlist，添加 attr="paid"，包含排名和 ranktime。
    """
    items = []
    
    # 查找"热门付费文章"标题
    h2 = soup.find('h2', class_='list-title', string=lambda s: '热门付费文章' in s if s else False)
    if not h2:
        return items
    
    # 向上找到 mps 容器
    mps_div = h2.find_parent('div', class_='mps')
    if not mps_div:
        return items
    
    # 在 mps 中找 ul.top10
    ul = mps_div.find('ul', class_='top10')
    if not ul:
        return items
    
    # 提取文章链接，保留排名和关键词
    for li in ul.find_all('li'):
        a = li.find('a', href=True)
        if not a:
            continue
        
        href = a['href']
        title = a.get_text(strip=True)
        
        if len(title) < 10:
            continue
        
        # 提取排名（从 li 的 class 中，如 mp1, mp2, ...）
        rank = None
        li_classes = li.get('class', [])
        for cls in li_classes:
            if cls.startswith('mp') and len(cls) > 2:
                try:
                    rank = int(cls[2:])
                    break
                except ValueError:
                    pass
        
        # 提取 keywords
        keywords = li.get('data-keywords', '')
        
        link = resolve_link(href, base_url)
        if title and link:
            # 将 keywords 和 attr 放入 detail 字典
            detail = {}
            if keywords:
                detail["keywords"] = keywords
            detail["attr"] = "paid"  # 添加 attr 到 detail
            
            items.append(NewsItem(
                title=title, 
                link=link, 
                section='hotlist',  # 改为 hotlist
                rank=rank, 
                ranktime='48hour',
                attr='paid',  # 添加 attr 字段
                detail=detail if detail else None
            ))
    
    return items
