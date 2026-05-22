"""GitHub Trending 页面解析器。

返回 NewsItem 列表，section=hotlist，根据 since 参数设置不同的 ranktime。
其他字段（desc, language, stars）存入 detail。
"""
from bs4 import BeautifulSoup
from news_homepage_parser.fetcher import fetch
from news_homepage_parser.models import NewsItem


# since 参数到 ranktime 的映射
_RANKTIME_MAP = {
    "daily": "24hour",
    "weekly": "168hour",
    "monthly": "720hour",
}


def fetch_trending(since: str = "daily") -> tuple[bool, list[NewsItem] | str]:
    """
    抓取并解析 GitHub Trending 页面。
    since: "daily" | "weekly" | "monthly"
    返回 (True, items) 或 (False, error_message)
    """
    valid = {"daily", "weekly", "monthly"}
    if since not in valid:
        return (False, f"Invalid since value: {since!r}. Must be one of {valid}")

    url = f"https://github.com/trending?since={since}"
    ok, html_or_err = fetch(url)
    if not ok:
        return (False, html_or_err)

    items = _parse(html_or_err, since)
    return (True, items)


def _parse(html: str, since: str) -> list[NewsItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    
    # 获取对应的 ranktime
    ranktime = _RANKTIME_MAP.get(since, "24hour")

    for rank, repo in enumerate(soup.select("article.Box-row"), start=1):
        # title: "owner / repo-name"
        h2 = repo.find("h2")
        if not h2:
            continue
        title = " ".join(h2.get_text().split())  # 压缩空白

        # url
        a = h2.find("a", href=True)
        if not a:
            continue
        url = "https://github.com" + a["href"]

        # description
        desc_tag = repo.find("p")
        desc = desc_tag.get_text(strip=True) if desc_tag else ""

        # language
        lang_tag = repo.find(attrs={"itemprop": "programmingLanguage"})
        language = lang_tag.get_text(strip=True) if lang_tag else ""

        # stars (今日/本周/本月新增 star)
        star_span = repo.find("span", class_=lambda c: c and "d-inline-block" in c and "float-sm-right" in c)
        if not star_span:
            # 总 star 数：第一个 svg.octicon-star 的父 <a>
            star_a = repo.find("a", href=lambda h: h and h.endswith("/stargazers"))
            star_span = star_a if star_a else None
        stars = star_span.get_text(strip=True) if star_span else ""

        # 构建 detail 字典，包含除 title 和 url 之外的所有字段
        detail = {}
        if desc:
            detail["desc"] = desc
        if language:
            detail["language"] = language
        if stars:
            detail["stars"] = stars
        
        items.append(NewsItem(
            title=title,
            link=url,
            section="hotlist",
            rank=rank,
            ranktime=ranktime,
            detail=detail if detail else None
        ))

    return items
