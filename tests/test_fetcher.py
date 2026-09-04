import unittest
from unittest.mock import patch, MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from news_homepage_parser.fetcher import fetch


def _make_playwright_mock(status_code: int, html: str = ""):
    """构造模拟 Playwright 调用链的 mock 对象。"""
    mock_response = MagicMock()
    mock_response.status = status_code

    mock_page = MagicMock()
    mock_page.goto.return_value = mock_response
    mock_page.content.return_value = html
    mock_page.wait_for_load_state.return_value = None

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_chromium = MagicMock()
    mock_chromium.launch.return_value = mock_browser

    mock_pw = MagicMock()
    mock_pw.chromium = mock_chromium
    mock_pw.__enter__ = MagicMock(return_value=mock_pw)
    mock_pw.__exit__ = MagicMock(return_value=False)

    return mock_pw


class TestFetchUnitTests(unittest.TestCase):

    def test_http_200_returns_html(self):
        """HTTP 200 时正常返回 HTML 内容"""
        mock_pw = _make_playwright_mock(200, "<html><body>Hello</body></html>")
        with patch("news_homepage_parser.fetcher.sync_playwright", return_value=mock_pw):
            success, content = fetch("https://example.com")
        self.assertTrue(success)
        self.assertEqual(content, "<html><body>Hello</body></html>")

    def test_http_404_returns_error_with_status_code(self):
        """HTTP 404 时返回含状态码的错误"""
        mock_pw = _make_playwright_mock(404)
        with patch("news_homepage_parser.fetcher.sync_playwright", return_value=mock_pw):
            success, message = fetch("https://example.com")
        self.assertFalse(success)
        self.assertIn("404", message)

    def test_http_500_returns_error_with_status_code(self):
        """HTTP 500 时返回含状态码的错误"""
        mock_pw = _make_playwright_mock(500)
        with patch("news_homepage_parser.fetcher.sync_playwright", return_value=mock_pw):
            success, message = fetch("https://example.com")
        self.assertFalse(success)
        self.assertIn("500", message)

    def test_timeout_returns_timeout_error(self):
        """请求超时时返回超时错误"""
        mock_pw = MagicMock()
        mock_pw.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw.__exit__ = MagicMock(return_value=False)
        mock_pw.chromium.launch.return_value.new_context.return_value.new_page.return_value.goto.side_effect = PlaywrightTimeout("timeout")
        with patch("news_homepage_parser.fetcher.sync_playwright", return_value=mock_pw):
            success, message = fetch("https://example.com")
        self.assertFalse(success)
        self.assertIn("timed out", message.lower())
        self.assertIn("30", message)

    def test_network_error_returns_network_error(self):
        """网络错误时返回网络错误信息"""
        mock_pw = MagicMock()
        mock_pw.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw.__exit__ = MagicMock(return_value=False)
        mock_pw.chromium.launch.return_value.new_context.return_value.new_page.return_value.goto.side_effect = Exception("Connection refused")
        with patch("news_homepage_parser.fetcher.sync_playwright", return_value=mock_pw):
            success, message = fetch("https://example.com")
        self.assertFalse(success)
        self.assertIn("Network error", message)
        self.assertIn("Connection refused", message)

    def test_none_response_returns_error(self):
        """goto 返回 None 时返回错误"""
        mock_pw = MagicMock()
        mock_pw.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw.__exit__ = MagicMock(return_value=False)
        mock_pw.chromium.launch.return_value.new_context.return_value.new_page.return_value.goto.return_value = None
        with patch("news_homepage_parser.fetcher.sync_playwright", return_value=mock_pw):
            success, message = fetch("https://example.com")
        self.assertFalse(success)
        self.assertIn("No response", message)


# Feature: news-homepage-parser, Property 2: Non-200 HTTP status returns error containing status code
class TestFetchProperty2(unittest.TestCase):

    @settings(max_examples=100)
    @given(
        status_code=st.one_of(
            st.integers(min_value=1, max_value=199),
            st.integers(min_value=201, max_value=599),
        )
    )
    def test_non_200_status_returns_error_containing_status_code(self, status_code):
        """
        Property 2: Non-200 HTTP status returns error containing status code
        Validates: Requirements 2.3
        """
        mock_pw = _make_playwright_mock(status_code)
        with patch("news_homepage_parser.fetcher.sync_playwright", return_value=mock_pw):
            success, message = fetch("https://example.com")
        assert not success, f"Expected failure for status {status_code}, got success"
        assert str(status_code) in message, (
            f"Expected status code {status_code} in error message, got: {message!r}"
        )


if __name__ == "__main__":
    unittest.main()
