"""Tests for FeedPoller.fetch() using mocked HTTP responses."""

from unittest.mock import MagicMock

import pytest

from core import FeedPoller

SAMPLE_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>Test RSS feed</description>
    <item>
      <title>First Item</title>
      <link>https://example.com/1</link>
      <guid>https://example.com/1</guid>
      <description>Summary of &lt;b&gt;first&lt;/b&gt; item</description>
      <pubDate>Thu, 01 May 2025 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Second Item</title>
      <link>https://example.com/2</link>
      <guid>https://example.com/2</guid>
      <description>Summary of second item</description>
      <pubDate>Thu, 01 May 2025 11:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""


def _mock_response(content, status_code=200, headers=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.content = content.encode("utf-8") if isinstance(content, str) else content
    mock.headers = headers or {}
    mock.raise_for_status = MagicMock()
    return mock


def _make_poller(response=None, status_code=200, headers=None, content=SAMPLE_RSS):
    if response is None:
        response = _mock_response(content, status_code=status_code, headers=headers)
    session = MagicMock()
    session.get.return_value = response
    return FeedPoller(session=session, timeout=10), session


FEED = {"name": "Test", "url": "https://example.com/rss", "enabled": True}


class TestFetchNewItems:
    def test_returns_two_items_for_fresh_feed(self):
        poller, _ = _make_poller()
        new_ids, new_notifs, state = poller.fetch(FEED, {}, set())
        assert len(new_ids) == 2
        assert len(new_notifs) == 2
        assert state.get("initialized") is True
        assert state.get("last_error") is None

    def test_deduplicates_seen_items(self):
        poller, _ = _make_poller()
        seen = {"https://example.com/1"}
        new_ids, new_notifs, _ = poller.fetch(FEED, {}, seen)
        assert len(new_ids) == 1
        assert new_ids[0] == "https://example.com/2"

    def test_all_seen_returns_empty(self):
        poller, _ = _make_poller()
        seen = {"https://example.com/1", "https://example.com/2"}
        new_ids, new_notifs, _ = poller.fetch(FEED, {}, seen)
        assert new_ids == []
        assert new_notifs == []


class TestSilentMode:
    def test_silent_returns_ids_but_no_notifs(self):
        poller, _ = _make_poller()
        new_ids, new_notifs, _ = poller.fetch(FEED, {}, set(), silent=True)
        assert len(new_ids) == 2
        assert new_notifs == []

    def test_silent_still_marks_initialized(self):
        poller, _ = _make_poller()
        _, _, state = poller.fetch(FEED, {}, set(), silent=True)
        assert state.get("initialized") is True


class TestConditionalGet:
    def test_304_returns_empty_with_no_error(self):
        poller, _ = _make_poller(status_code=304, content="")
        new_ids, new_notifs, state = poller.fetch(FEED, {}, set())
        assert new_ids == []
        assert new_notifs == []
        assert state.get("last_error") is None

    def test_stores_etag_from_response(self):
        poller, _ = _make_poller(headers={"ETag": '"abc123"'})
        _, _, state = poller.fetch(FEED, {}, set())
        assert state.get("etag") == '"abc123"'

    def test_sends_etag_when_known(self):
        poller, session = _make_poller()
        poller.fetch(FEED, {"etag": '"known-etag"'}, set())
        call_headers = session.get.call_args.kwargs.get("headers") or {}
        assert call_headers.get("If-None-Match") == '"known-etag"'

    def test_stores_last_modified_from_response(self):
        poller, _ = _make_poller(headers={"Last-Modified": "Thu, 01 May 2025 10:00:00 GMT"})
        _, _, state = poller.fetch(FEED, {}, set())
        assert state.get("last_modified") == "Thu, 01 May 2025 10:00:00 GMT"

    def test_sends_last_modified_when_known(self):
        poller, session = _make_poller()
        lm = "Thu, 01 May 2025 10:00:00 GMT"
        poller.fetch(FEED, {"last_modified": lm}, set())
        call_headers = session.get.call_args.kwargs.get("headers") or {}
        assert call_headers.get("If-Modified-Since") == lm


class TestErrorHandling:
    def test_raises_on_http_error(self):
        mock = MagicMock()
        mock.status_code = 500
        mock.raise_for_status.side_effect = Exception("500 Server Error")
        session = MagicMock()
        session.get.return_value = mock
        poller = FeedPoller(session=session, timeout=10)
        with pytest.raises(Exception, match="500"):
            poller.fetch(FEED, {}, set())

    def test_raises_on_network_error(self):
        session = MagicMock()
        session.get.side_effect = ConnectionError("network unreachable")
        poller = FeedPoller(session=session, timeout=10)
        with pytest.raises(ConnectionError):
            poller.fetch(FEED, {}, set())


class TestNotificationFields:
    def test_required_fields_present(self):
        poller, _ = _make_poller()
        _, notifs, _ = poller.fetch(FEED, {}, set())
        required = {
            "id",
            "title",
            "link",
            "feed_title",
            "timestamp",
            "summary",
            "created_at",
            "opened_at",
            "read_at",
            "archived_at",
        }
        for notif in notifs:
            assert required.issubset(notif.keys()), f"Missing keys in {notif}"

    def test_opened_at_and_read_at_are_none(self):
        poller, _ = _make_poller()
        _, notifs, _ = poller.fetch(FEED, {}, set())
        for notif in notifs:
            assert notif["opened_at"] is None
            assert notif["read_at"] is None
            assert notif["archived_at"] is None

    def test_summary_is_html_stripped(self):
        poller, _ = _make_poller()
        _, notifs, _ = poller.fetch(FEED, {}, set())
        # Find the First Item notification specifically
        first_item = next(n for n in notifs if n["title"] == "First Item")
        assert "<b>" not in first_item["summary"]
        assert "first" in first_item["summary"]
