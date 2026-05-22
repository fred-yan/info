from urllib.parse import urlparse


def validate_url(url: str) -> tuple[bool, str]:
    """
    验证 URL 合法性。
    返回 (True, url) 表示验证通过，返回 (False, error_message) 表示验证失败。
    """
    # Requirements 1.3: 检查 URL 非空
    if not url or not url.strip():
        return (False, "URL is required")

    # 尝试解析 URL
    try:
        parsed = urlparse(url)
    except Exception:
        return (False, "Invalid URL format")

    # Requirements 1.4: 检查 scheme 为 http 或 https
    if parsed.scheme not in ("http", "https"):
        return (False, f"Invalid URL scheme: {parsed.scheme}")

    # Requirements 1.5: 检查 URL 格式合法（有 netloc）
    if not parsed.netloc:
        return (False, "Invalid URL format")

    # Requirements 1.1, 1.2: URL 合法，返回成功
    return (True, url)
