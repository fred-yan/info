import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from .models import ParseResult
from .validator import validate_url
from .fetcher import fetch
from .extractor import extract
from .pretty_printer import to_json, to_table

logger = logging.getLogger(__name__)

# 需要点击 tab 后二次抓取的网站配置
# key: 域名关键字, value: (第一次 click_selector, 第二次 click_selector)
_TAB_SITES: dict[str, list[str | None]] = {
    "cn.wsj.com": [None, "text=本周"],
}

# 需要使用 HTTP/1.1 的网站（HTTP/2 有问题）
_HTTP1_SITES = {"washingtonpost.com", "cn.wsj.com"}

# 需要非 headless 模式的网站
# 注意：云服务器无 X Server 时需安装 xvfb 或改为空集合
_NON_HEADLESS_SITES: set[str] = set()  # 云服务器部署时置空


def parse(url: str, output_format: str = "json") -> ParseResult:
    """
    顶层入口：验证 → 抓取 → 提取 → 返回 ParseResult。
    捕获所有未处理异常，返回结构化错误响应。
    """
    now = datetime.now(timezone.utc)

    try:
        # 1. 验证 URL
        valid, error_or_url = validate_url(url)
        if not valid:
            logger.warning("parse invalid url=%s error=%s", url, error_or_url)
            return ParseResult(url=url, fetched_at=now, error=error_or_url)

        canonical_url = error_or_url
        domain = urlparse(canonical_url).netloc.lower()
        logger.info("parse start url=%s", canonical_url)

        # 2. 抓取 HTML（支持多 tab 网站）
        tab_selectors = next(
            (v for k, v in _TAB_SITES.items() if k in domain), None
        )
        use_http1 = any(site in domain for site in _HTTP1_SITES)
        headless = not any(site in domain for site in _NON_HEADLESS_SITES)

        if tab_selectors:
            # 多次抓取，每次点击不同 tab，合并 HTML 片段
            combined_html_parts = []
            for selector in tab_selectors:
                ok, html_or_error = fetch(canonical_url, click_selector=selector, use_http1=use_http1, headless=headless)
                if not ok:
                    return ParseResult(url=url, fetched_at=now, error=html_or_error)
                combined_html_parts.append(html_or_error)
            # 将多段 HTML 拼接，extractor 会分别解析
            html_or_error = "\n<!-- TAB_SEPARATOR -->\n".join(combined_html_parts)
        else:
            ok, html_or_error = fetch(canonical_url, use_http1=use_http1, headless=headless)
            if not ok:
                return ParseResult(url=url, fetched_at=now, error=html_or_error)

        # 3. 提取新闻条目
        items, most_read, warnings = extract(html_or_error, url)

        for w in warnings:
            logger.warning("extractor warning url=%s msg=%s", url, w)
        logger.info("parse done url=%s items=%d most_read=%d", url, len(items), len(most_read))

        return ParseResult(
            url=url,
            fetched_at=now,
            items=items,
            total=len(items),
            most_read=most_read,
            warnings=warnings,
        )

    except Exception as e:
        logger.error("Unhandled exception in parse()", exc_info=True)
        return ParseResult(
            url=url,
            fetched_at=now,
            error=f"{type(e).__name__}: {str(e)}",
        )
