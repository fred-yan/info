"""
Tests for news_homepage_parser.validator.validate_url

Unit tests (2.2) + Property-based test P1 (2.3)
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from news_homepage_parser.validator import validate_url


# ---------------------------------------------------------------------------
# 2.2 Unit Tests
# ---------------------------------------------------------------------------


class TestValidateUrlEmpty:
    """Requirements 1.3 — empty / blank URL must return an error."""

    def test_empty_string(self):
        ok, msg = validate_url("")
        assert ok is False
        assert "required" in msg.lower()

    def test_whitespace_only(self):
        ok, msg = validate_url("   ")
        assert ok is False
        assert "required" in msg.lower()

    def test_none_like_empty(self):
        # Passing an empty string (closest to None without type error)
        ok, msg = validate_url("")
        assert ok is False


class TestValidateUrlInvalidScheme:
    """Requirements 1.4 — non-http/https scheme must return an error."""

    def test_ftp_scheme(self):
        ok, msg = validate_url("ftp://example.com")
        assert ok is False
        assert "scheme" in msg.lower()

    def test_file_scheme(self):
        ok, msg = validate_url("file:///etc/passwd")
        assert ok is False
        assert "scheme" in msg.lower()

    def test_mailto_scheme(self):
        ok, msg = validate_url("mailto:user@example.com")
        assert ok is False

    def test_no_scheme(self):
        ok, msg = validate_url("example.com/path")
        assert ok is False


class TestValidateUrlMalformed:
    """Requirements 1.5 — malformed URLs must return an error."""

    def test_missing_netloc(self):
        ok, msg = validate_url("http://")
        assert ok is False
        assert "invalid" in msg.lower()

    def test_just_scheme(self):
        ok, msg = validate_url("https://")
        assert ok is False

    def test_plain_text(self):
        ok, msg = validate_url("not a url at all")
        assert ok is False


class TestValidateUrlValid:
    """Requirements 1.1, 1.2 — valid http/https URLs must pass validation."""

    def test_http_url(self):
        ok, url = validate_url("http://example.com")
        assert ok is True
        assert url == "http://example.com"

    def test_https_url(self):
        ok, url = validate_url("https://www.bbc.com")
        assert ok is True
        assert url == "https://www.bbc.com"

    def test_https_with_path(self):
        ok, url = validate_url("https://www.economist.com/news/2024")
        assert ok is True

    def test_https_with_query(self):
        ok, url = validate_url("https://cnn.com/search?q=news")
        assert ok is True

    def test_http_with_port(self):
        ok, url = validate_url("http://localhost:8080/page")
        assert ok is True


# ---------------------------------------------------------------------------
# 2.3 Property-Based Test P1
# ---------------------------------------------------------------------------

# Feature: news-homepage-parser, Property 1: Invalid URL validation


def _non_http_https_urls():
    """
    Strategy that generates URL-like strings that are NOT valid http/https URLs.
    Covers:
      - empty / blank strings  (Req 1.3)
      - non-http/https schemes (Req 1.4)
      - malformed strings      (Req 1.5)
    """
    invalid_schemes = ["ftp", "file", "mailto", "ssh", "ws", "wss", "data", "javascript", ""]
    scheme_based = st.builds(
        lambda scheme, host: f"{scheme}://{host}" if scheme else host,
        scheme=st.sampled_from(invalid_schemes),
        host=st.from_regex(r"[a-z]{3,10}\.[a-z]{2,4}", fullmatch=True),
    )
    blank_strings = st.text(alphabet=" \t\n", min_size=0, max_size=10)
    random_text = st.text(min_size=0, max_size=50).filter(
        lambda s: not s.startswith("http://") and not s.startswith("https://")
    )
    return st.one_of(blank_strings, scheme_based, random_text)


@settings(max_examples=100)
@given(url=_non_http_https_urls())
def test_property_1_invalid_url_always_returns_error(url: str):
    # Feature: news-homepage-parser, Property 1: Invalid URL validation
    # Validates: Requirements 1.3, 1.4, 1.5
    ok, msg = validate_url(url)
    assert ok is False, (
        f"validate_url({url!r}) returned ok=True but expected an error"
    )
    assert isinstance(msg, str) and len(msg) > 0
