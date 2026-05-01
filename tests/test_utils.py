"""Tests for utility functions: preview_text, display_title, entry_identifier, and dates."""

from datetime import datetime

from core import (
    display_title,
    entry_identifier,
    feed_key,
    now_iso,
    parse_iso_datetime,
    preview_text,
)


class TestPreviewText:
    def test_strips_html_tags(self):
        entry = {"summary": "<p>Hello <b>world</b></p>"}
        result = preview_text(entry)
        assert "<" not in result
        assert "Hello world" in result

    def test_truncates_at_140(self):
        entry = {"summary": "A" * 200}
        result = preview_text(entry)
        assert len(result) <= 143  # 140 chars + "..."
        assert result.endswith("...")

    def test_exact_140_not_truncated(self):
        entry = {"summary": "A" * 140}
        result = preview_text(entry)
        assert not result.endswith("...")

    def test_falls_back_to_link_when_empty_summary(self):
        entry = {"summary": "", "link": "https://example.com/article"}
        result = preview_text(entry)
        assert result == "https://example.com/article"

    def test_falls_back_to_description(self):
        entry = {"description": "Some description"}
        result = preview_text(entry)
        assert result == "Some description"

    def test_empty_entry_returns_empty_string(self):
        assert preview_text({}) == ""


class TestDisplayTitle:
    def test_short_title_unchanged(self):
        item = {"title": "Short title"}
        assert display_title(item) == "Short title"

    def test_truncates_long_title(self):
        item = {"title": "X" * 100}
        result = display_title(item)
        assert result.endswith("...")
        assert len(result) <= 64

    def test_includes_timestamp_when_present(self):
        item = {"title": "Article", "timestamp": "01-05-25 10:00"}
        result = display_title(item)
        assert result.startswith("[01-05-25 10:00]")
        assert "Article" in result

    def test_no_brackets_without_timestamp(self):
        item = {"title": "Article"}
        result = display_title(item)
        assert "[" not in result
        assert result == "Article"

    def test_missing_title_falls_back(self):
        item = {}
        result = display_title(item)
        assert result == "No title"

    def test_custom_max_len(self):
        item = {"title": "A" * 20}
        result = display_title(item, max_len=10)
        assert len(result) <= 10
        assert result.endswith("...")


class TestEntryIdentifier:
    FEED = {"url": "https://example.com/rss"}

    def test_prefers_id_field(self):
        entry = {"id": "unique-id", "link": "https://example.com/1"}
        assert entry_identifier(self.FEED, entry) == "unique-id"

    def test_falls_back_to_link(self):
        entry = {"link": "https://example.com/1"}
        assert entry_identifier(self.FEED, entry) == "https://example.com/1"

    def test_falls_back_to_feed_url_plus_title(self):
        entry = {"title": "My Article"}
        result = entry_identifier(self.FEED, entry)
        assert result == "https://example.com/rss::My Article"

    def test_empty_entry_uses_untitled(self):
        entry = {}
        result = entry_identifier(self.FEED, entry)
        assert "untitled" in result


class TestParseIsoDatetime:
    def test_parses_valid_iso(self):
        result = parse_iso_datetime("2025-05-01T10:00:00")
        assert result == datetime(2025, 5, 1, 10, 0, 0)

    def test_returns_none_for_none(self):
        assert parse_iso_datetime(None) is None

    def test_returns_none_for_empty_string(self):
        assert parse_iso_datetime("") is None

    def test_returns_none_for_invalid_string(self):
        assert parse_iso_datetime("not-a-date") is None


class TestNowIso:
    def test_returns_valid_iso_string(self):
        result = now_iso()
        parsed = parse_iso_datetime(result)
        assert parsed is not None

    def test_does_not_include_microseconds(self):
        result = now_iso()
        assert "." not in result  # timespec="seconds"


class TestFeedKey:
    def test_uses_url(self):
        assert feed_key({"url": "https://example.com/rss"}) == "https://example.com/rss"

    def test_falls_back_to_name(self):
        assert feed_key({"name": "My Feed"}) == "My Feed"

    def test_default_when_empty(self):
        assert feed_key({}) == "unknown-feed"
