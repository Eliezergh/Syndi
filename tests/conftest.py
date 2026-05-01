"""
Shared fixtures for Syndi's test suite.
Adds 'src/' to sys.path so 'import core' works without installation.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure the src directory is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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


@pytest.fixture
def sample_feed() -> dict:
    return {"name": "Test Feed", "url": "https://example.com/rss", "enabled": True}


@pytest.fixture
def sample_config_dict() -> dict:
    return {
        "feeds": [{"name": "HN", "url": "https://news.ycombinator.com/rss", "enabled": True}],
        "check_interval_seconds": 300,
        "request_timeout_seconds": 10,
        "notification_enabled": True,
        "show_preview": True,
        "startup_silent_sync": True,
        "max_recent_items": 50,
        "max_stored_notifications": 500,
        "max_menu_notifications": 12,
    }


@pytest.fixture
def config_file(tmp_path, sample_config_dict) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(sample_config_dict), encoding="utf-8")
    return path


@pytest.fixture
def data_path(tmp_path) -> Path:
    return tmp_path / "data.json"


@pytest.fixture
def rss_response() -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.content = SAMPLE_RSS.encode("utf-8")
    mock.headers = {}
    mock.raise_for_status = MagicMock()
    return mock
