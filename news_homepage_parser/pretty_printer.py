import json
from io import StringIO
from datetime import datetime

from rich.console import Console
from rich.table import Table

from .models import NewsItem, ParseResult


def _group_by_section(items: list[NewsItem]) -> list[dict]:
    """将 NewsItem 列表按 section 分组，保持原始顺序，返回分组列表。
    
    每篇文章保留自身的 section 字段和原始索引（用于 round-trip 反序列化）。
    同时在 section 级别添加 ranktime 和 attr 字段（如果该组所有文章都有相同值）。
    
    分组键规则：
    - 使用 (section, ranktime, attr) 组合作为分组键
    - 这样可以区分相同 section 但不同 ranktime 或 attr 的文章
    """
    groups: dict[tuple, list[dict]] = {}  # 使用 (section, ranktime, attr) 作为键
    group_metadata: dict[tuple, dict] = {}  # 存储每个分组的 ranktime 和 attr
    order: list[tuple] = []
    
    for idx, item in enumerate(items):
        section_key = item.section or "Uncategorized"
        ranktime_key = item.ranktime  # 可以是 None
        attr_key = item.attr  # 可以是 None
        key = (section_key, ranktime_key, attr_key)
        
        if key not in groups:
            groups[key] = []
            group_metadata[key] = {"ranktime": item.ranktime, "attr": item.attr}
            order.append(key)
        
        article_dict = {
            "title": item.title,
            "link": item.link,
            "section": item.section,  # 保留原始 section（可为 null）
            "_idx": idx,              # 原始顺序索引，用于 round-trip
        }
        # 添加可选字段
        if item.rank is not None:
            article_dict["rank"] = item.rank
        if item.is_original is not None:
            article_dict["is_original"] = item.is_original
        if item.ranktime is not None:
            article_dict["ranktime"] = item.ranktime
        if item.attr is not None:
            article_dict["attr"] = item.attr
        if item.detail is not None:
            article_dict["detail"] = item.detail
        groups[key].append(article_dict)
    
    # 构建返回结果，在 section 级别添加 ranktime 和 attr
    result = []
    for section_key, ranktime_key, attr_key in order:
        key = (section_key, ranktime_key, attr_key)
        section_dict = {"section": section_key, "articles": groups[key]}
        # 添加 section 级别的 ranktime 和 attr
        if group_metadata[key]["ranktime"] is not None:
            section_dict["ranktime"] = group_metadata[key]["ranktime"]
        if group_metadata[key]["attr"] is not None:
            section_dict["attr"] = group_metadata[key]["attr"]
        result.append(section_dict)
    
    return result


def to_json(result: ParseResult) -> str:
    """序列化 ParseResult 为 JSON 字符串，items 按 section 分组。"""
    data = {
        "url": result.url,
        "fetched_at": result.fetched_at.isoformat(),
        "total": result.total,
        "warnings": result.warnings,
        "error": result.error,
        "sections": _group_by_section(result.items),
        "most_read": [
            {
                "title": item.title,
                "link": item.link,
                "section": item.section,
                **({"rank": item.rank} if item.rank is not None else {}),
                **({"is_original": item.is_original} if item.is_original is not None else {}),
                **({"ranktime": item.ranktime} if item.ranktime is not None else {}),
                **({"attr": item.attr} if item.attr is not None else {}),
                **({"detail": item.detail} if item.detail is not None else {}),
            }
            for item in result.most_read
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def to_table(result: ParseResult) -> str:
    """使用 rich 渲染格式化表格，返回字符串。"""
    title = (
        f"News: {result.url} | "
        f"Fetched at: {result.fetched_at.isoformat()} | "
        f"Total: {result.total}"
    )
    table = Table(title=title, show_lines=True)
    table.add_column("title", style="bold")
    table.add_column("link")
    table.add_column("section")

    for item in result.items:
        table.add_row(item.title, item.link, item.section or "")

    buf = StringIO()
    console = Console(file=buf, highlight=False, width=10000)
    console.print(table)
    return buf.getvalue()


def from_json(json_str: str) -> tuple[bool, list[NewsItem] | str]:
    """从 JSON 字符串反序列化为 NewsItem 列表。

    支持新的 sections 分组格式和旧的 items 平铺格式。
    返回 (True, items) 或 (False, error_message)。
    """
    try:
        data = json.loads(json_str)
        if "sections" not in data and "items" not in data:
            raise KeyError("missing 'sections' or 'items' key")
        indexed: list[tuple[int, NewsItem]] = []
        if "sections" in data:
            for group in data["sections"]:
                for entry in group.get("articles", []):
                    # 使用 article 自身的 section 字段（保留 null）
                    item = NewsItem(
                        title=entry["title"],
                        link=entry["link"],
                        section=entry.get("section"),
                        rank=entry.get("rank"),
                        is_original=entry.get("is_original"),
                        ranktime=entry.get("ranktime"),
                        attr=entry.get("attr"),
                        detail=entry.get("detail"),
                    )
                    idx = entry.get("_idx", len(indexed))
                    indexed.append((idx, item))
            # 按原始索引排序，恢复插入顺序
            indexed.sort(key=lambda t: t[0])
            items = [item for _, item in indexed]
        else:
            items = [
                NewsItem(
                    title=entry["title"],
                    link=entry["link"],
                    section=entry.get("section"),
                    rank=entry.get("rank"),
                    is_original=entry.get("is_original"),
                    ranktime=entry.get("ranktime"),
                    attr=entry.get("attr"),
                    detail=entry.get("detail"),
                )
                for entry in data["items"]
            ]
        return True, items
    except Exception as e:
        return False, f"Deserialization failed: {str(e)}"
