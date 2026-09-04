import os
import time
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

# Cloudflare Challenge 页面的特征文本（出现这些说明还在被拦截）
_CF_CHALLENGE_MARKERS = [
    "enable JavaScript and disable any ad blocker",
    "Just a moment",
    "Checking your browser",
    "DDoS protection by Cloudflare",
    "Please wait while we verify",
]


def _is_cf_challenge(html: str) -> bool:
    """检测 HTML 内容是否是 Cloudflare Challenge 拦截页。"""
    for marker in _CF_CHALLENGE_MARKERS:
        if marker.lower() in html.lower():
            return True
    return False


def fetch(url: str, timeout: int = 60, click_selector: str | None = None, use_http1: bool = False, headless: bool = True, cf_wait: int = 0, wait_after: int = 2) -> tuple[bool, str]:
    """
    使用 Playwright（headless Chromium）抓取页面，返回 (True, html_content) 或 (False, error_message)。
    能绕过大多数反爬机制（Cloudflare、JS 渲染等）。

    click_selector: 可选 CSS 选择器，页面加载后点击该元素再抓取（用于 tab 切换等场景）。
    use_http1: 强制使用 HTTP/1.1（某些网站的 HTTP/2 有问题）
    headless: 是否使用无头模式（调试时可设为 False）
    cf_wait: Cloudflare Challenge 额外等待秒数（0=不等待，>0=等待 JS Challenge 执行完成）
    wait_after: domcontentloaded 后额外等待秒数，用于 SPA 异步渲染（默认 2s）
    """
    timeout_ms = timeout * 1000
    logger.info("fetch start url=%s click=%s use_http1=%s headless=%s", url, click_selector, use_http1, headless)
    t0 = time.monotonic()
    
    # Washington Post 等网站需要禁用 HTTP/2
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
    ]
    if headless:
        launch_args.append("--headless=new")
    if use_http1:
        launch_args.append("--disable-http2")
    
    try:
        with sync_playwright() as p:
            # 代理配置：从环境变量 PLAYWRIGHT_PROXY 读取
            # 只对国际网站使用代理，国内网站直连
            proxy_url = os.environ.get("PLAYWRIGHT_PROXY")
            _NO_PROXY_DOMAINS = {
                "ftchinese.com", "36kr.com", "huxiu.com", "zaobao.com",
                "zhihu.com", "weibo.cn", "thepaper.cn", "tmtpost.com",
            }
            use_proxy = False
            if proxy_url:
                # 检查 URL 是否是国内网站
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.lower()
                use_proxy = not any(d in domain for d in _NO_PROXY_DOMAINS)

            launch_kwargs = {
                "headless": headless,
                "args": launch_args,
            }
            if use_proxy and proxy_url:
                launch_kwargs["proxy"] = {"server": proxy_url}
                logger.info("fetch using proxy: %s", proxy_url)

            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                extra_http_headers={
                    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Upgrade-Insecure-Requests": "1",
                },
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
            )
            # 隐藏 webdriver 标志，绕过 headless 检测
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = context.new_page()
            # wait_until="domcontentloaded" 只等 DOM 解析完成，不等后台请求
            response = page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            if response is None:
                browser.close()
                return (False, "No response received")
            status = response.status
            if status != 200:
                browser.close()
                logger.warning("fetch failed url=%s http_status=%d", url, status)
                return (False, f"HTTP error: {status}")
            # 额外等待让 JS 渲染主要内容，SPA 站点需要更长时间
            time.sleep(wait_after)
            # Cloudflare Challenge 处理：等待 JS Challenge 完成后的真实页面
            if cf_wait > 0:
                logger.info("fetch cf_wait=%ds url=%s", cf_wait, url)
                deadline = time.monotonic() + cf_wait
                while time.monotonic() < deadline:
                    current_html = page.content()
                    if not _is_cf_challenge(current_html):
                        logger.info("fetch cf_challenge passed url=%s", url)
                        break
                    time.sleep(1)
                else:
                    # 超时仍是 Challenge 页
                    current_html = page.content()
                    if _is_cf_challenge(current_html):
                        browser.close()
                        logger.warning("fetch cf_challenge timeout url=%s", url)
                        return (False, "Cloudflare challenge not resolved within timeout")
            # 非 headless 调试模式：额外停留 30 秒供人工观察页面状态
            if not headless:
                logger.info("fetch [DEBUG] non-headless pause 30s for inspection url=%s", url)
                time.sleep(30)
            if click_selector:
                try:
                    logger.info("Attempting to click selector: %s", click_selector)
                    # 支持 "text=XXX" 格式的文本匹配
                    if click_selector.startswith("text="):
                        text_val = click_selector[5:]
                        # 不使用 exact=True，因为可能有多个匹配
                        elements = page.get_by_text(text_val).all()
                        logger.info("Found %d elements matching text '%s'", len(elements), text_val)
                        if elements:
                            # 点击第一个可见的元素
                            for elem in elements:
                                if elem.is_visible():
                                    logger.info("Clicking visible element")
                                    elem.click()
                                    break
                    else:
                        # CSS 选择器
                        elem = page.locator(click_selector).first
                        logger.info("Found element matching selector '%s'", click_selector)
                        if elem.is_visible():
                            logger.info("Clicking element")
                            elem.click()
                        else:
                            logger.warning("Element not visible")
                    # 点击后等待内容变化
                    logger.info("Waiting for content to change after click")
                    # 等待足够的时间让 AJAX 请求完成并渲染
                    time.sleep(5)
                        
                except Exception as e:
                    logger.error("Click failed: %s", e)
                    pass  # 点击失败不影响主流程
            # 等待页面导航稳定再取内容（防止 JS 重定向导致 content() 报错）
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass  # 超时或已稳定，继续
            html = page.content()
            browser.close()
            elapsed = time.monotonic() - t0
            logger.info("fetch ok url=%s elapsed=%.1fs html_len=%d", url, elapsed, len(html))
            return (True, html)
    except PlaywrightTimeout:
        logger.error("fetch timeout url=%s timeout=%ds", url, timeout)
        return (False, f"Request timed out after {timeout} seconds")
    except Exception as e:
        logger.error("fetch error url=%s error=%s", url, e, exc_info=True)
        return (False, f"Network error: {str(e)}")
