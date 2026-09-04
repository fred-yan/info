"""端到端集成测试（mock Playwright fetch）"""
import json
from unittest.mock import patch, MagicMock

from news_homepage_parser.parser import parse
from news_homepage_parser.pretty_printer import to_json

SAMPLE_HTML = """
<html><body>
  <article>
    <h2><a href="/news/test-article">Test Article Title</a></h2>
  </article>
</body></html>
"""


# 1. 完整流程：合法 URL + mock fetch 返回 HTML → 返回 ParseResult 含 items
def test_full_pipeline_returns_items():
    with patch("news_homepage_parser.parser.fetch", return_value=(True, SAMPLE_HTML)):
        result = parse("https://example.com")

    assert result.error is None
    assert result.total > 0
    assert len(result.items) == result.total
    assert result.items[0].title == "Test Article Title"


# 2. URL 验证失败：空 URL → ParseResult.error 非空
def test_empty_url_returns_error():
    result = parse("")
    assert result.error is not None
    assert len(result.error) > 0


# 3. HTTP 失败：mock fetch 返回 500 错误 → ParseResult.error 含 "500"
def test_http_500_returns_error_with_status_code():
    with patch("news_homepage_parser.parser.fetch", return_value=(False, "HTTP error: 500")):
        result = parse("https://example.com")

    assert result.error is not None
    assert "500" in result.error


# 4. 组件抛出异常：mock fetch 抛出 RuntimeError → ParseResult.error 含异常信息（顶层兜底）
def test_fetch_raises_exception_returns_structured_error():
    with patch("news_homepage_parser.parser.fetch", side_effect=RuntimeError("boom")):
        result = parse("https://example.com")

    assert result.error is not None
    assert "RuntimeError" in result.error
    assert "boom" in result.error


# 5. 完整流程 JSON 输出：验证 to_json(result) 包含 url、total、fetched_at、most_read 字段
def test_full_pipeline_json_output_contains_required_fields():
    with patch("news_homepage_parser.parser.fetch", return_value=(True, SAMPLE_HTML)):
        result = parse("https://example.com")

    output = to_json(result)
    data = json.loads(output)

    assert "url" in data
    assert "total" in data
    assert "fetched_at" in data
    assert "most_read" in data
    assert "sections" in data
    assert data["url"] == "https://example.com"
