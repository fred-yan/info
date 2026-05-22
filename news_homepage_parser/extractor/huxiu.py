from bs4 import BeautifulSoup
from news_homepage_parser.models import NewsItem
from ._utils import resolve_link


def extract(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """
    虎嗅专用策略：只提取 48 小时热文榜（带排名，不去重）。
    section 命名为 hotlist，添加 ranktime=48hour。
    is_original=True 的文章添加 attr="original"。
    """
    items = []
    
    wrap = soup.find("div", class_="hot-article-wrap")
    if not wrap:
        return items
    
    rank = 0
    for child in wrap.children:
        if not hasattr(child, "name") or child.name != "div":
            continue
        if "article-wrap" not in " ".join(child.get("class", [])):
            continue
        info = child.find("div", class_="article-wrap__info")
        if not info:
            continue
        a = info.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        if "/article/" not in href:
            continue
        link = resolve_link(href, base_url)
        title = a.get_text(strip=True)
        if not title:
            continue
        
        # 检测并移除"原创"标签
        is_original = False
        if title.startswith("原创"):
            is_original = True
            title = title[2:].strip()  # 移除"原创"两个字
        
        rank += 1
        
        # 如果是原创，添加 attr 和 detail
        attr_value = "original" if is_original else None
        detail = {"attr": "original"} if is_original else None
        
        items.append(NewsItem(
            title=title, 
            link=link, 
            section="hotlist",  # 改为 hotlist
            rank=rank,
            ranktime="48hour",  # 添加 ranktime
            attr=attr_value,  # 添加 attr（仅原创文章）
            detail=detail  # 添加 detail（仅原创文章）
        ))

    return items


def extract_first_section(soup: BeautifulSoup, base_url: str) -> list[NewsItem]:
    """
    提取首页第一个栏目的文章（约 3 篇）。
    section 命名为 section_1。
    is_original=True 的文章添加 attr="original"。
    """
    items = []
    
    # 查找 home-top section
    home_top = soup.find("section", class_="home-top")
    if not home_top:
        return items
    
    seen_urls = set()
    
    # 遍历所有文章链接
    for a in home_top.find_all("a", href=lambda x: x and "/article/" in x):
        href = a.get("href", "")
        
        # 去重
        if href in seen_urls:
            continue
        seen_urls.add(href)
        
        # 查找标题
        title = None
        
        # 方法1: 查找 title 类的元素
        title_elem = a.find(["h2", "h3", "h4", "div", "span"], 
                           class_=lambda x: x and "title" in " ".join(x).lower())
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 方法2: 查找 img 的 alt
        if not title or len(title) < 5:
            img = a.find("img")
            if img and img.get("alt"):
                title = img.get("alt")
        
        # 方法3: 使用 a 标签的文本（排除短文本）
        if not title or len(title) < 5:
            text = a.get_text(strip=True)
            if text and len(text) > 5 and len(text) < 200:
                title = text
        
        if title and len(title) > 5:
            # 检测并移除"原创"标签
            is_original = False
            if title.startswith("原创"):
                is_original = True
                title = title[2:].strip()  # 移除"原创"两个字
            
            # 如果是原创，添加 attr 和 detail
            attr_value = "original" if is_original else None
            detail = {"attr": "original"} if is_original else None
            
            link = resolve_link(href, base_url)
            items.append(NewsItem(
                title=title, 
                link=link, 
                section="section_1",  # 改为 section_1
                attr=attr_value,  # 添加 attr（仅原创文章）
                detail=detail  # 添加 detail（仅原创文章）
            ))
            
            # 只提取前 3 篇
            if len(items) >= 3:
                break
    
    return items
