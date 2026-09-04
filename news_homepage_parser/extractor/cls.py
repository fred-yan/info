"""
财联社热门文章排行榜提取器

通过普通 HTTP 请求获取 https://www.cls.cn/ 首页 HTML，
页面为服务端渲染，排行榜数据直接在 HTML 中，无需 Playwright。

HTML 结构：
  <div>热门文章排行榜</div>
  <div class="b-t-w-1 b-s-s b-c-e6e7ea">       ← next sibling
    <div class="c-b m-r-20 m-l-20 ...">          ← 每一行
      <div class="f-l m-t-4 ... w-14 ...">1</div>   ← 排名数字
      <div class="f-l w-219 ...">
        <a href="/detail/2472584" ...>标题</a>
      </div>
    </div>
    ...
  </div>
"""
import logging
import urllib.request
import urllib.error
from bs4 import BeautifulSoup
from news_homepage_parser.models import NewsItem

logger = logging.getLogger(__name__)

_HOME_URL = "https://www.cls.cn/"
_BASE_URL = "https://www.cls.cn"


def fetch_hot_articles() -> list[NewsItem]:
    """
    直接 HTTP 请求财联社首页，解析热门文章排行榜。
    返回 section="hotlist", rank=榜单位置(1-based) 的 NewsItem 列表。
    """
    req = urllib.request.Request(
        _HOME_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        logger.error("cls http error: %s", e)
        return []
    except Exception as e:
        logger.error("cls fetch error: %s", e)
        return []

    soup = BeautifulSoup(html, "html.parser")
    return extract(soup)


def extract(soup: BeautifulSoup) -> list[NewsItem]:
    """
    从已解析的 BeautifulSoup 对象中提取热门文章排行榜。
    可供 extractor/__init__.py 分发调用（Playwright 路径）或直接 HTTP 调用。
    """
    items: list[NewsItem] = []

    # 1. 定位"热门文章排行榜"标题 div
    title_div = soup.find(
        lambda tag: tag.name == "div"
        and tag.string and "热门文章排行榜" in tag.string
    )
    if not title_div:
        logger.warning("cls: '热门文章排行榜' title div not found")
        return items

    # 2. 找其父级容器的 next sibling（含榜单列表）
    # 标题 div 的父 div 的 next sibling 是榜单容器
    parent = title_div.parent
    list_container = parent.find_next_sibling("div") if parent else None
    if not list_container:
        # 尝试直接用 title_div 的 next sibling
        list_container = title_div.find_next_sibling("div")
    if not list_container:
        logger.warning("cls: list container not found after title div")
        return items

    # 3. 遍历每一条榜单项（div.c-b）
    seen_urls: set[str] = set()
    for row in list_container.find_all("div", recursive=True):
        # 找包含排名数字的 div（class 含 w-14 和 h-14）
        rank_div = row.find("div", class_=lambda c: c and "w-14" in c and "h-14" in c)
        if not rank_div:
            continue

        rank_text = rank_div.get_text(strip=True)
        if not rank_text.isdigit():
            continue
        rank = int(rank_text)

        # 找文章链接
        a = row.find("a", href=lambda h: h and "/detail/" in h)
        if not a:
            continue

        href = a["href"]
        title = a.get_text(strip=True)
        if not title:
            continue

        # 构造完整 URL
        if href.startswith("http"):
            link = href
        else:
            link = _BASE_URL + href

        if link in seen_urls:
            continue
        seen_urls.add(link)

        items.append(NewsItem(
            title=title,
            link=link,
            section="hotlist",
            rank=rank,
            ranktime="",
        ))

    # 按 rank 排序（防止 DOM 顺序乱序）
    items.sort(key=lambda x: x.rank or 999)
    logger.info("cls extracted %d hot articles", len(items))
    return items
