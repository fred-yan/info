"""微博热搜获取器。

接口：https://m.weibo.cn/api/container/getIndex
提取实时热点 card_group，返回 rank, title, url
"""
import logging
import requests
from news_homepage_parser.models import NewsItem

logger = logging.getLogger(__name__)

_API = "https://m.weibo.cn/api/container/getIndex"
_PARAMS = {
    "containerid": "106003type%3D25%26t%3D3%26disable_hot%3D1%26filter_type%3Drealtimehot",
    "title": "%E5%BE%AE%E5%8D%9A%E7%83%AD%E6%90%9C",
    "extparam": "filter_type%3Drealtimehot%26mi_cid%3D100103%26pos%3D0_0%26c_type%3D30%26display_time%3D1540538388",
    "luicode": "10000011",
    "lfid": "231583",
}
_TIMEOUT = 15
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://m.weibo.cn/",
    "X-Requested-With": "XMLHttpRequest",
    "Cookie": (
        "SUB=_2AkMeQLuzf8NxqwFRmv0RzG_ib41yww_EieKoHEpoJRM3HRl-yT9yqnAItRB6NcCVXXkC6PpY_RcEoXdQhWo9RQiN4LXc; "
        "SUBP=0033WrSXqPxfM72-Ws9jqgMF55529P9D9WhY-kco02QVoHpDj_NslCS6; "
        "WEIBOCN_FROM=1110006030; "
        "MLOGIN=0; "
        "XSRF-TOKEN=e013c4; "
        "mweibo_short_token=6b9819e325; "
        "M_WEIBOCN_PARAMS=luicode%3D10000011%26lfid%3D231583%26fid%3D106003type%253D25%2526t%253D3%2526disable_hot%253D1%2526filter_type%3Drealtimehot%26uicode%3D10000011"
    ),
}


def fetch_hot_search() -> tuple[bool, list[NewsItem] | str]:
    """
    返回 (True, items) 或 (False, error_message)。
    items 按接口原始顺序，包含 rank, title, url。
    """
    try:
        logger.info("weibo start fetching hot_search")
        resp = requests.get(_API, params=_PARAMS, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 432:
            return (False, "Weibo API requires authentication (HTTP 432). Cookie may be expired.")
        resp.raise_for_status()
        story_data = resp.json()
    except Exception as e:
        logger.error("weibo fetch hot_search failed error=%s", e, exc_info=True)
        return (False, f"Failed to fetch weibo hot search: {e}")

    # 解析数据
    if not (story_data.get("ok") and story_data.get("data")):
        return (False, "Invalid response structure")

    cards = story_data["data"].get("cards", [])
    result = []
    rank = 1

    for card in cards:
        # 找到"实时热点"卡片
        if "title" not in card or "实时热点" not in card.get("title", ""):
            continue
        if "card_group" not in card:
            continue

        for card_group in card["card_group"]:
            # 必须同时有 scheme, desc, desc_extr 才是热搜条目
            if not all(k in card_group for k in ("scheme", "desc", "desc_extr")):
                logger.debug("weibo skip non-hot-search item desc=%s", card_group.get("desc", ""))
                continue

            title = card_group["desc"]
            url = card_group["scheme"]
            result.append(NewsItem(
                title=title,
                link=url,
                section="hotlist",
                rank=rank,
                ranktime="24hour",
                detail={}
            ))
            rank += 1

    logger.info("weibo hot_search fetched count=%d", len(result))
    return (True, result)
