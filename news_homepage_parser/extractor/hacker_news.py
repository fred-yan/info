"""Hacker News Top Stories 获取器。

流程：
1. GET /v0/topstories.json  → 全量 story id 列表（约 500 条）
2. 并发 GET /v0/item/{id}.json 获取详情
3. 过滤过去 24 小时内的 story，按 score 降序，取前 100 条
"""
import time
import logging
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from news_homepage_parser.models import NewsItem

logger = logging.getLogger(__name__)

_BASE = "https://hacker-news.firebaseio.com/v0"
_TOP_N = 100
_WORKERS = 5   # 并发线程数
_TIMEOUT = 10  # 单次请求超时秒数


def fetch_top_stories() -> tuple[bool, list[NewsItem] | str]:
    """
    返回 (True, items) 或 (False, error_message)。
    只保留过去 24 小时内发布的 story，按 score 降序，最多 100 条。
    """
    # 1. 获取 top story id 列表
    try:
        resp = requests.get(f"{_BASE}/topstories.json", timeout=_TIMEOUT)
        resp.raise_for_status()
        story_ids: list[int] = resp.json()
    except Exception as e:
        logger.error("hacker_news fetch topstories failed error=%s", e, exc_info=True)
        return (False, f"Failed to fetch top stories: {e}")

    logger.info("hacker_news topstories total_ids=%d", len(story_ids))

    # 2. 只取前 200 条（列表已按热度排序，无需全部拉取）
    story_ids = story_ids[:200]

    # 3. 并发拉取 story 详情
    stories = _fetch_items(story_ids)

    # 4. 过滤：24 小时内 + 有效字段，按 score 降序，取前 100
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    cutoff_ts = cutoff.timestamp()

    valid = [
        s for s in stories
        if s.get("score") is not None
        and s.get("title")
        and s.get("time", 0) >= cutoff_ts
    ]
    valid.sort(key=lambda s: s["score"], reverse=True)
    top = valid[:_TOP_N]

    logger.info("hacker_news 24h stories total=%d top=%d", len(valid), len(top))

    # 4. 格式化输出为 NewsItem
    result = []
    for rank, item in enumerate(top, start=1):
        ts = item.get("time")
        time_str = (
            datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            if ts else ""
        )
        
        # score 和 time 放入 detail
        detail = {
            "score": item.get("score", 0),
            "time": time_str
        }
        
        result.append(NewsItem(
            title=item.get("title", ""),
            link=item.get("url", f"https://news.ycombinator.com/item?id={item['id']}"),
            section="hotlist",
            rank=rank,
            ranktime="24hour",
            detail=detail
        ))

    return (True, result)


def _fetch_items(ids: list[int]) -> list[dict]:
    """并发拉取 item 详情，忽略失败的条目。"""
    results = []

    def _get(story_id: int) -> dict | None:
        for attempt in range(2):  # 最多重试 1 次
            try:
                r = requests.get(f"{_BASE}/item/{story_id}.json", timeout=_TIMEOUT)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                if attempt == 0:
                    time.sleep(0.5)  # 短暂等待后重试
                else:
                    logger.debug("hacker_news item fetch failed id=%d error=%s", story_id, e)
        return None

    with ThreadPoolExecutor(max_workers=_WORKERS) as executor:
        futures = {executor.submit(_get, sid): sid for sid in ids}
        for future in as_completed(futures):
            item = future.result()
            if item and item.get("type") == "story":
                results.append(item)

    return results
