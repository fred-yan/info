"""
Tests for news_homepage_parser/extractor.py
Unit tests (5.3) + Property-based tests P3 (5.4), P4 (5.5), P7 (5.6)
"""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from news_homepage_parser.extractor import extract


# ---------------------------------------------------------------------------
# Unit Tests (5.3)
# ---------------------------------------------------------------------------

class TestSectionExtraction:
    """测试含 section 标签的 HTML 正确提取 section。"""

    def test_section_from_section_tag_with_heading(self):
        html = """
        <section>
          <h2>Technology</h2>
          <article>
            <h2>AI breakthrough</h2>
            <a href="/ai">Read more</a>
          </article>
        </section>
        """
        items, _, warnings = extract(html, "https://example.com")
        assert len(items) == 1
        assert items[0].section == "Technology"

    def test_section_from_aria_label(self):
        html = """
        <section aria-label="Sports">
          <article>
            <h2>World Cup 2024</h2>
            <a href="/sports/worldcup">Read</a>
          </article>
        </section>
        """
        items, _, warnings = extract(html, "https://example.com")
        assert len(items) == 1
        assert items[0].section == "Sports"

    def test_no_section_returns_none(self):
        html = """
        <article>
          <h2>Breaking News</h2>
          <a href="/news/1">Read</a>
        </article>
        """
        items, _, warnings = extract(html, "https://example.com")
        assert len(items) == 1
        assert items[0].section is None


class TestNoNewsItems:
    """测试无新闻条目时返回空列表和警告。"""

    def test_empty_html_returns_empty_and_warning(self):
        items, _, warnings = extract("", "https://example.com")
        assert items == []
        assert any("no news items found" in w for w in warnings)

    def test_html_without_articles_or_headings(self):
        html = "<html><body><p>No news here</p></body></html>"
        items, _, warnings = extract(html, "https://example.com")
        assert items == []
        assert any("no news items found" in w for w in warnings)

    def test_article_without_link_skipped(self):
        html = """
        <article>
          <h2>Title without link</h2>
        </article>
        """
        items, _, warnings = extract(html, "https://example.com")
        assert items == []
        assert any("no news items found" in w for w in warnings)


class TestEconomistStrategy:
    """测试 Economist 站点 HTML 提取（新版结构）。"""

    BASE_URL = "https://www.economist.com"

    def test_extracts_articles_with_target_section(self):
        html = """
        <div>
          <h3><a href="/topics/business">Business</a></h3>
          <ul>
            <li>
              <h3><a href="/business/ai-future">The future of AI</a></h3>
            </li>
            <li>
              <h3><a href="/business/markets">Global markets</a></h3>
            </li>
          </ul>
        </div>
        """
        items, _, warnings = extract(html, self.BASE_URL)
        assert len(items) == 2
        assert items[0].title == "The future of AI"
        assert items[0].link == "https://www.economist.com/business/ai-future"
        assert items[0].section == "Business"
        assert items[1].title == "Global markets"

    def test_relative_links_resolved(self):
        html = """
        <div>
          <h3><a href="/topics/finance-and-economics">Finance & economics</a></h3>
          <ul>
            <li><h3><a href="/economy/report">Economy report</a></h3></li>
          </ul>
        </div>
        """
        items, _, warnings = extract(html, self.BASE_URL)
        assert len(items) == 1
        assert items[0].link.startswith("https://")

    def test_no_generic_warning_for_economist(self):
        html = """
        <div>
          <h3><a href="/topics/business">Business</a></h3>
          <ul>
            <li><h3><a href='/test'>Test</a></h3></li>
          </ul>
        </div>
        """
        _, _, warnings = extract(html, self.BASE_URL)
        assert not any("Generic" in w for w in warnings)


class TestGenericStrategy:
    """测试未知站点触发通用策略。"""

    BASE_URL = "https://www.unknownsite.com"

    def test_generic_warning_present(self):
        html = """
        <article>
          <h2>Generic News</h2>
          <a href="/news/1">Read</a>
        </article>
        """
        items, _, warnings = extract(html, self.BASE_URL)
        assert any("Generic extraction strategy applied" in w for w in warnings)

    def test_generic_extracts_articles(self):
        html = """
        <article>
          <h2>First Story</h2>
          <a href="/story/1">Read</a>
        </article>
        <article>
          <h2>Second Story</h2>
          <a href="/story/2">Read</a>
        </article>
        """
        items, _, warnings = extract(html, self.BASE_URL)
        assert len(items) == 2
        assert items[0].title == "First Story"

    def test_generic_fallback_to_h2(self):
        html = """
        <h2><a href="/news/1">Headline One</a></h2>
        <h2><a href="/news/2">Headline Two</a></h2>
        """
        items, _, warnings = extract(html, self.BASE_URL)
        assert len(items) == 2

    def test_deduplication(self):
        html = """
        <article>
          <h2>Duplicate Story</h2>
          <a href="/story/1">Read</a>
        </article>
        <article>
          <h2>Duplicate Story</h2>
          <a href="/story/1">Read</a>
        </article>
        """
        items, _, warnings = extract(html, self.BASE_URL)
        assert len(items) == 1


# ---------------------------------------------------------------------------
# Property-Based Tests
# ---------------------------------------------------------------------------

# Helpers for generating HTML fragments
_title_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
    min_size=1,
    max_size=50,
).filter(lambda t: t.strip())

_path_segment = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
    min_size=1,
    max_size=20,
)

_relative_path = st.builds(lambda s: f"/{s}", _path_segment)

_absolute_url = st.builds(
    lambda host, path: f"https://{host}.com{path}",
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=10),
    _relative_path,
)

_base_url = st.builds(
    lambda host: f"https://{host}.com",
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=10).filter(
        lambda h: h not in ("economist", "bbc", "cnn")
    ),
)


def _make_article_html(title: str, href: str) -> str:
    return f"<article><h2>{title}</h2><a href='{href}'>link</a></article>"


# Feature: news-homepage-parser, Property 3: All extracted NewsItems have non-empty title and absolute URL link
@settings(max_examples=100)
@given(
    titles=st.lists(_title_text, min_size=1, max_size=5),
    hrefs=st.lists(_absolute_url, min_size=1, max_size=5),
    base_url=_base_url,
)
def test_p3_all_items_have_nonempty_title_and_absolute_link(titles, hrefs, base_url):
    """
    Property 3: All extracted NewsItems have non-empty title and absolute URL link
    Validates: Requirements 3.2, 3.3
    """
    # Pair titles and hrefs (zip to shortest)
    pairs = list(zip(titles, hrefs))
    html = "".join(_make_article_html(t, h) for t, h in pairs)
    items, _, _ = extract(html, base_url)
    for item in items:
        assert item.title.strip() != "", f"Empty title found: {item!r}"
        assert item.link.startswith("http://") or item.link.startswith("https://"), (
            f"Non-absolute link found: {item.link!r}"
        )


# Feature: news-homepage-parser, Property 4: Relative URLs are resolved to absolute
@settings(max_examples=100)
@given(
    titles=st.lists(_title_text, min_size=1, max_size=5),
    paths=st.lists(_relative_path, min_size=1, max_size=5),
    base_url=_base_url,
)
def test_p4_relative_urls_resolved_to_absolute(titles, paths, base_url):
    """
    Property 4: Relative URLs are resolved to absolute
    Validates: Requirements 3.6
    """
    pairs = list(zip(titles, paths))
    html = "".join(_make_article_html(t, p) for t, p in pairs)
    items, _, _ = extract(html, base_url)
    for item in items:
        assert item.link.startswith("http://") or item.link.startswith("https://"), (
            f"Relative link not resolved: {item.link!r} (base_url={base_url!r})"
        )


# Feature: news-homepage-parser, Property 7: Generic extraction strategy notice in warnings
@settings(max_examples=100)
@given(
    html=st.just("<article><h2>Test</h2><a href='/test'>link</a></article>"),
    host=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz",
        min_size=3,
        max_size=10,
    ).filter(lambda h: h not in ("economist", "bbc", "cnn", "apnews", "ftchinese", "wsj", "kr", "huxiu", "36kr")),
)
def test_p7_generic_strategy_notice_in_warnings(html, host):
    """
    Property 7: Generic extraction strategy notice in warnings
    Validates: Requirements 6.4
    """
    base_url = f"https://{host}.com"
    _, _, warnings = extract(html, base_url)
    assert any("Generic extraction strategy applied" in w for w in warnings), (
        f"Expected generic strategy warning for base_url={base_url!r}, got warnings={warnings!r}"
    )
