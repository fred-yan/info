"""
extractor 包：根据域名分发到对应站点解析模块。
对外只暴露 extract() 函数，接口与原 extractor.py 完全兼容。
"""
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import logging
from news_homepage_parser.models import NewsItem
from ._utils import dedup

from . import economist, apnews, ftchinese, wsj, kr36, huxiu, washingtonpost, zaobao, tmtpost, theverge, techcrunch, mittr, generic

logger = logging.getLogger(__name__)


def extract(html: str, base_url: str) -> tuple[list[NewsItem], list[NewsItem], list[str]]:
    """
    从 HTML 中提取 NewsItem 列表。
    根据 base_url 域名分发到对应策略模块。
    返回 (items, most_read, warnings)。
    """
    warnings: list[str] = []
    most_read: list[NewsItem] = []
    skip_dedup = False  # 标记是否跳过去重

    domain = urlparse(base_url).netloc.lower()
    logger.info("extract start domain=%s html_len=%d", domain, len(html))

    if "huxiu.com" in domain:
        soup = BeautifulSoup(html, "html.parser")
        items = huxiu.extract(soup, base_url)
        first_section_items = huxiu.extract_first_section(soup, base_url)
        items.extend(first_section_items)
        skip_dedup = True
        strategy = "huxiu"
    elif "zaobao.com" in domain:
        soup = BeautifulSoup(html, "html.parser")
        items = zaobao.extract(soup, base_url)
        skip_dedup = True
        strategy = "zaobao"
    elif "wsj.com" in domain:
        items = wsj.extract(html, base_url)
        skip_dedup = True
        strategy = "wsj"
    else:
        soup = BeautifulSoup(html, "html.parser")
        if "economist.com" in domain:
            items = economist.extract(soup, base_url)
            most_read = economist.extract_most_read(soup, base_url)
            skip_dedup = True
            strategy = "economist"
        elif "washingtonpost.com" in domain:
            items = washingtonpost.extract(soup, base_url)
            most_read = washingtonpost.extract_most_read(soup, base_url)
            strategy = "washingtonpost"
        elif "apnews.com" in domain:
            items = apnews.extract(soup, base_url)
            most_read = apnews.extract_most_read(soup, base_url)
            strategy = "apnews"
        elif "ftchinese.com" in domain:
            focus_items = ftchinese.extract(soup, base_url)
            items = focus_items
            hot_articles = ftchinese.extract_hot_articles(soup, base_url)
            hot_premium = ftchinese.extract_hot_premium(soup, base_url)
            items.extend(hot_articles)
            items.extend(hot_premium)
            skip_dedup = True
            strategy = "ftchinese"
        elif "36kr.com" in domain:
            items = kr36.extract(soup, base_url)
            skip_dedup = True
            strategy = "kr36"
        elif "tmtpost.com" in domain:
            items = tmtpost.extract(soup, base_url)
            skip_dedup = True
            strategy = "tmtpost"
        elif "theverge.com" in domain:
            items = theverge.extract(soup, base_url)
            skip_dedup = True
            strategy = "theverge"
        elif "techcrunch.com" in domain:
            items = techcrunch.extract(soup, base_url)
            skip_dedup = True
            strategy = "techcrunch"
        elif "technologyreview.com" in domain:
            items = mittr.extract(soup, base_url)
            skip_dedup = True
            strategy = "mittr"
        else:
            logger.warning("extract using generic fallback domain=%s", domain)
            warnings.append("Generic extraction strategy applied")
            items = generic.extract(soup, base_url)
            strategy = "generic"

    items = [i for i in items if i.title.strip() and i.link]
    most_read = [i for i in most_read if i.title.strip() and i.link]
    if not skip_dedup:
        items = dedup(items)
    most_read = dedup(most_read)

    if not items:
        logger.warning("extract found 0 items domain=%s strategy=%s", domain, strategy)
        warnings.append("Warning: no news items found on this page")

    logger.info("extract done domain=%s strategy=%s items=%d most_read=%d",
                domain, strategy, len(items), len(most_read))
    return (items, most_read, warnings)
