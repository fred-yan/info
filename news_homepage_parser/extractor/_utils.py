"""共享工具函数：链接解析、去重、section 提取。"""
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from news_homepage_parser.models import NewsItem


def resolve_link(href: str, base_url: str) -> str:
    """将相对链接解析为绝对 URL。"""
    if not href:
        return ""
    return urljoin(base_url, href)


def dedup(items: list[NewsItem]) -> list[NewsItem]:
    """按 link 去重，保留第一条。"""
    seen: set[str] = set()
    result = []
    for item in items:
        if item.link not in seen:
            seen.add(item.link)
            result.append(item)
    return result


def find_direct_heading(parent_tag) -> str | None:
    """查找父元素的直接子 heading（不深入 article/div 等容器）。"""
    for child in parent_tag.children:
        if hasattr(child, "name") and child.name in ("h1", "h2", "h3", "h4"):
            text = child.get_text(strip=True)
            if text:
                return text
    return None


def find_section(tag, soup) -> str | None:
    """从最近的 <section> 或含 section/category 类名的父元素提取 section 名称。"""
    for parent in tag.parents:
        if parent.name == "section":
            label = parent.get("aria-label") or parent.get("data-section")
            if label:
                return label.strip()
            text = find_direct_heading(parent)
            if text:
                return text
            return None
        classes = parent.get("class", [])
        classes_str = " ".join(classes) if isinstance(classes, list) else str(classes)
        if any(kw in classes_str.lower() for kw in ("section", "category")):
            label = parent.get("aria-label") or parent.get("data-section")
            if label:
                return label.strip()
            text = find_direct_heading(parent)
            if text:
                return text
    return None


def section_from_path(path: str) -> str | None:
    """从 URL 路径第一段提取栏目名，如 /middle-east-and-africa/... -> Middle East And Africa"""
    parts = [p for p in path.split("/") if p]
    if not parts:
        return None
    return parts[0].replace("-", " ").title()
