from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class NewsItem:
    title: str                    # 新闻标题，非空字符串
    link: str                     # 绝对 URL
    section: Optional[str] = None # 栏目名称，无则为 None
    rank: Optional[int] = None    # 热度排名（用于热门文章等）
    is_original: Optional[bool] = None # 是否为原创内容
    ranktime: Optional[str] = None # 榜单时间范围（如 48hour）
    attr: Optional[str] = None    # 属性标记（如 paid）
    detail: Optional[dict] = None # 详细信息（如 {"desc": "...", "keywords": "...", "attr": "..."}）


@dataclass
class ParseResult:
    url: str                              # 来源 URL
    fetched_at: datetime                  # 抓取时间戳
    items: list[NewsItem] = field(default_factory=list)
    total: int = 0                        # 等于 len(items)
    most_read: list[NewsItem] = field(default_factory=list)  # 订阅者最多阅读
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None           # 顶层错误信息（如有）
