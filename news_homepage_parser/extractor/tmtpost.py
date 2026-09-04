"""
钛媒体热文榜提取器
提取 https://www.tmtpost.com/new 页面右侧热文榜列表。

HTML 结构（JS 渲染后）：
  <div class="newHot">
    <ul>
      <li>
        <a href="https://www.tmtpost.com/{id}.html">
          <div class="hotAll">
            <img ...>   <!-- 前3名有排名 badge 图片，无文字 -->
            文章标题文本
          </div>
        </a>
      </li>
      ...
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
    提取热文榜列表。
    section="hotlist", rank=列表顺序(1-based), ranktime=""
    """
    items: list[NewsItem] = []

    hot_div = soup.find("div", class_="newHot")
    if not hot_div:
        logger.warning("tmtpost: .newHot container not found")
        return items

    ul = hot_div.find("ul")
    if not ul:
        logger.warning("tmtpost: ul not found in .newHot")
        return items

    for rank, li in enumerate(ul.find_all("li", recursive=False), start=1):
        a = li.find("a", href=True)
        if not a:
            continue

        href = a["href"]
        # 只保留文章链接（含文章 ID 数字的路径）
        if not href or "tmtpost.com/" not in href:
            continue

        # 提取标题：取 div.hotAll 的纯文字节点，排除 img 的 alt
        hot_div_inner = a.find("div", class_="hotAll")
        if hot_div_inner:
            # 只取直接文字节点，不含子标签的文本
            title = "".join(
                t.strip()
                for t in hot_div_inner.children
                if hasattr(t, "string") and t.string
            ).strip()
            # 备用：get_text 过滤掉纯空白
            if not title:
                title = hot_div_inner.get_text(separator="", strip=True)
        else:
            title = a.get_text(strip=True)

        if not title or len(title) < 3:
            continue

        link = resolve_link(href, base_url)

        items.append(NewsItem(
            title=title,
            link=link,
            section="hotlist",
            rank=rank,
            ranktime="",
        ))

    logger.info("tmtpost extracted %d hot articles", len(items))
    return items
