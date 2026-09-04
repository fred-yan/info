import json
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from news_homepage_parser.models import NewsItem, ParseResult
from news_homepage_parser.pretty_printer import from_json, to_json, to_table

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(items=None, url="https://example.com", warnings=None, error=None):
    items = items or []
    return ParseResult(
        url=url,
        fetched_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        items=items,
        total=len(items),
        warnings=warnings or [],
        error=error,
    )


# ---------------------------------------------------------------------------
# 6.4 Unit tests
# ---------------------------------------------------------------------------

class TestToJson:
    def test_contains_required_fields(self):
        result = _make_result()
        output = json.loads(to_json(result))
        assert "url" in output
        assert "fetched_at" in output
        assert "total" in output
        assert "sections" in output
        assert "warnings" in output

    def test_url_value(self):
        result = _make_result(url="https://news.ycombinator.com")
        output = json.loads(to_json(result))
        assert output["url"] == "https://news.ycombinator.com"

    def test_fetched_at_is_iso_string(self):
        result = _make_result()
        output = json.loads(to_json(result))
        # Should be parseable as ISO datetime
        parsed = datetime.fromisoformat(output["fetched_at"])
        assert parsed is not None

    def test_total_field(self):
        items = [NewsItem(title="T", link="https://a.com")]
        result = _make_result(items=items)
        output = json.loads(to_json(result))
        assert output["total"] == 1

    def test_section_none_serialized_as_null(self):
        items = [NewsItem(title="T", link="https://a.com", section=None)]
        result = _make_result(items=items)
        output = json.loads(to_json(result))
        # section=None → grouped under "Uncategorized"
        assert output["sections"][0]["section"] == "Uncategorized"

    def test_section_value_preserved(self):
        items = [NewsItem(title="T", link="https://a.com", section="World")]
        result = _make_result(items=items)
        output = json.loads(to_json(result))
        assert output["sections"][0]["section"] == "World"

    def test_indent_formatting(self):
        result = _make_result()
        raw = to_json(result)
        # indent=2 means lines start with spaces
        assert "\n" in raw


class TestFromJson:
    def test_valid_json_returns_items(self):
        items = [NewsItem(title="Hello", link="https://a.com", section="Tech")]
        result = _make_result(items=items)
        json_str = to_json(result)
        ok, data = from_json(json_str)
        assert ok is True
        assert len(data) == 1
        assert data[0].title == "Hello"
        assert data[0].link == "https://a.com"
        assert data[0].section == "Tech"

    def test_malicious_json_returns_error(self):
        ok, msg = from_json("{not valid json}")
        assert ok is False
        assert "Deserialization failed" in msg

    def test_empty_string_returns_error(self):
        ok, msg = from_json("")
        assert ok is False
        assert "Deserialization failed" in msg

    def test_missing_items_key_returns_error(self):
        ok, msg = from_json('{"url": "https://x.com"}')
        assert ok is False
        assert "Deserialization failed" in msg

    def test_section_null_deserialized_as_none(self):
        items = [NewsItem(title="T", link="https://a.com", section=None)]
        result = _make_result(items=items)
        ok, data = from_json(to_json(result))
        assert ok is True
        assert data[0].section is None


class TestToTable:
    def test_contains_column_headers(self):
        result = _make_result()
        output = to_table(result)
        assert "title" in output.lower()
        assert "link" in output.lower()
        assert "section" in output.lower()

    def test_contains_url_and_fetched_at(self):
        result = _make_result(url="https://bbc.com")
        output = to_table(result)
        assert "https://bbc.com" in output

    def test_contains_item_data(self):
        items = [NewsItem(title="Breaking News", link="https://bbc.com/news/1")]
        result = _make_result(items=items)
        output = to_table(result)
        assert "Breaking News" in output
        assert "https://bbc.com/news/1" in output


# ---------------------------------------------------------------------------
# 6.5 Property 5: Table output contains all required columns and item data
# ---------------------------------------------------------------------------

# Feature: news-homepage-parser, Property 5: Table output contains all required columns and item data

_printable_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"), whitelist_characters=" -_.,!?"),
    min_size=1,
    max_size=60,
)

news_item_strategy = st.builds(
    NewsItem,
    title=_printable_text,
    link=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=1,
        max_size=20,
    ).map(lambda p: f"https://example.com/{p}"),
    section=st.one_of(st.none(), _printable_text),
)


@settings(max_examples=100)
@given(items=st.lists(news_item_strategy, min_size=1, max_size=10))
def test_p5_table_contains_columns_and_data(items):
    # Feature: news-homepage-parser, Property 5: Table output contains all required columns and item data
    result = ParseResult(
        url="https://example.com",
        fetched_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        items=items,
        total=len(items),
    )
    output = to_table(result)
    lower = output.lower()
    # Column headers present
    assert "title" in lower
    assert "link" in lower
    assert "section" in lower
    # Each item's title and link appear in output
    for item in items:
        assert item.title in output
        assert item.link in output


# ---------------------------------------------------------------------------
# 6.6 Property 6: ParseResult round-trip serialization
# ---------------------------------------------------------------------------

# Feature: news-homepage-parser, Property 6: ParseResult round-trip serialization

_text = st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" -_"), min_size=1, max_size=60)
_link = st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz0123456789").map(lambda s: f"https://example.com/{s}")
_section = st.one_of(st.none(), _text)

_item_strategy = st.builds(NewsItem, title=_text, link=_link, section=_section)

_datetime_strategy = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2099, 12, 31),
    timezones=st.just(timezone.utc),
)

_url_strategy = st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz0123456789").map(
    lambda s: f"https://{s}.com"
)


@settings(max_examples=100)
@given(
    url=_url_strategy,
    fetched_at=_datetime_strategy,
    items=st.lists(_item_strategy, min_size=0, max_size=10),
)
def test_p6_round_trip_serialization(url, fetched_at, items):
    # Feature: news-homepage-parser, Property 6: ParseResult round-trip serialization
    result = ParseResult(
        url=url,
        fetched_at=fetched_at,
        items=items,
        total=len(items),
    )
    json_str = to_json(result)
    ok, deserialized = from_json(json_str)

    assert ok is True
    assert len(deserialized) == len(items)
    for original, restored in zip(items, deserialized):
        assert restored.title == original.title
        assert restored.link == original.link
        assert restored.section == original.section
