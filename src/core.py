"""
Syndi core — business logic isolated from UI for testability.

Covers: config, data I/O, notification inbox management,
feed polling, and shared utility functions.
"""

import json
import re
import tempfile
from datetime import datetime
from pathlib import Path
from time import mktime

import feedparser
import requests

APP_NAME = "Syndi"
APP_VERSION = "1.2"
DATA_SCHEMA_VERSION = 2

DEFAULT_CHECK_INTERVAL = 300
DEFAULT_MAX_HISTORY_ITEMS = 50
DEFAULT_MAX_STORED_NOTIFICATIONS = 500
DEFAULT_REQUEST_TIMEOUT = 10
DEFAULT_MENU_NOTIFICATION_LIMIT = 12
# These are built-in fallbacks; users can override them in config.json.
USER_AGENT = f"{APP_NAME} RSS Notifier/{APP_VERSION}"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class SyndiConfig:
    """Holds validated application configuration."""

    def __init__(self):
        self.feeds = []
        self.check_interval = DEFAULT_CHECK_INTERVAL
        self.notification_enabled = True
        self.show_preview = True
        self.max_recent_items = DEFAULT_MAX_HISTORY_ITEMS
        self.max_stored_notifications = DEFAULT_MAX_STORED_NOTIFICATIONS
        self.menu_notification_limit = DEFAULT_MENU_NOTIFICATION_LIMIT
        self.request_timeout = DEFAULT_REQUEST_TIMEOUT
        self.startup_silent_sync = True

    @classmethod
    def from_dict(cls, data: dict) -> "SyndiConfig":
        cfg = cls()
        cfg.feeds = data.get("feeds", [])
        cfg.check_interval = max(
            30,
            int(data.get("check_interval_seconds", DEFAULT_CHECK_INTERVAL)),
        )
        cfg.notification_enabled = bool(data.get("notification_enabled", True))
        cfg.show_preview = bool(data.get("show_preview", True))
        cfg.max_recent_items = max(10, int(data.get("max_recent_items", DEFAULT_MAX_HISTORY_ITEMS)))
        cfg.max_stored_notifications = max(
            cfg.max_recent_items,
            int(data.get("max_stored_notifications", DEFAULT_MAX_STORED_NOTIFICATIONS)),
        )
        cfg.menu_notification_limit = max(
            5,
            int(data.get("max_menu_notifications", DEFAULT_MENU_NOTIFICATION_LIMIT)),
        )
        cfg.request_timeout = max(
            3,
            int(data.get("request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT)),
        )
        cfg.startup_silent_sync = bool(data.get("startup_silent_sync", True))
        return cfg

    def to_dict(self) -> dict:
        return {
            "feeds": self.feeds,
            "check_interval_seconds": self.check_interval,
            "notification_enabled": self.notification_enabled,
            "show_preview": self.show_preview,
            "max_recent_items": self.max_recent_items,
            "max_stored_notifications": self.max_stored_notifications,
            "max_menu_notifications": self.menu_notification_limit,
            "request_timeout_seconds": self.request_timeout,
            "startup_silent_sync": self.startup_silent_sync,
        }


def load_config(config_path: Path) -> "tuple[SyndiConfig, Exception | None]":
    """Load and validate config.json. Returns (config, error_or_None)."""
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        return SyndiConfig.from_dict(data), None
    except Exception as exc:
        return SyndiConfig(), exc


def save_config(config_path: Path, raw_config: dict) -> None:
    """Atomically write a raw config dict to disk."""
    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=config_path.parent,
        encoding="utf-8",
    ) as handle:
        json.dump(raw_config, handle, ensure_ascii=False, indent=2)
        temp_path = Path(handle.name)
    temp_path.replace(config_path)


# ---------------------------------------------------------------------------
# Data I/O
# ---------------------------------------------------------------------------


def load_data(data_path: Path, max_stored: int) -> "tuple[set, list, dict, datetime | None]":
    """
    Load persisted state from data.json.
    Returns (seen_items, notifications, feed_state, last_check).
    Handles migration from the legacy 'recent_items' format.
    """
    if not data_path.exists():
        return set(), [], {}, None

    try:
        raw = json.loads(data_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return set(), [], {}, None
    seen_items = set(raw.get("seen_items", []))
    feed_state = raw.get("feed_state", {})
    last_check = parse_iso_datetime(raw.get("last_check"))

    if "notifications" in raw:
        notifications = raw["notifications"]
    else:
        notifications = _migrate_legacy_recent_items(raw.get("recent_items", []))

    # Migrate discarded_at -> archived_at (backward compat for pre-archive versions)
    for notif in notifications:
        if notif.get("discarded_at") and not notif.get("archived_at"):
            notif["archived_at"] = notif["discarded_at"]
            del notif["discarded_at"]

    notifications = trim_notifications(notifications, max_stored)
    return seen_items, notifications, feed_state, last_check


def _migrate_legacy_recent_items(legacy: list) -> list:
    result = []
    for i, item in enumerate(reversed(legacy)):
        result.append(
            {
                "id": item.get("id") or item.get("link") or f"legacy-{i}",
                "title": item.get("title", "No title"),
                "link": item.get("link", ""),
                "feed_title": item.get("feed_title", "Unknown feed"),
                "timestamp": item.get("timestamp", ""),
                "summary": item.get("summary", ""),
                "created_at": item.get("timestamp", ""),
                "opened_at": None,
                "read_at": None,
                "archived_at": None,
            }
        )
    return result


def save_data(
    data_path: Path,
    seen_items: set,
    notifications: list,
    feed_state: dict,
    last_check: "datetime | None",
    max_stored: int,
) -> None:
    """Atomically write data.json. Trims before writing."""
    notifications = trim_notifications(notifications, max_stored)
    payload = {
        "schema_version": DATA_SCHEMA_VERSION,
        "seen_items": sorted(seen_items),
        "notifications": notifications,
        "feed_state": feed_state,
        "last_check": last_check.isoformat() if last_check else None,
    }
    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=data_path.parent,
        encoding="utf-8",
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        temp_path = Path(handle.name)
    temp_path.replace(data_path)


# ---------------------------------------------------------------------------
# Notification inbox
# ---------------------------------------------------------------------------


def trim_notifications(notifications: list, max_stored: int) -> list:
    """Keep at most max_stored items, dropping archived ones before active ones."""
    if len(notifications) <= max_stored:
        return notifications
    active = [n for n in notifications if not n.get("archived_at")]
    archived = [n for n in notifications if n.get("archived_at")]
    return (active + archived)[:max_stored]


def find_notification(notifications: list, item_id: str) -> "dict | None":
    return next((item for item in notifications if item.get("id") == item_id), None)


def active_notifications(notifications: list) -> list:
    """Items that have not been archived."""
    return [item for item in notifications if not item.get("archived_at")]


def active_count(notifications: list) -> int:
    """Count active (not archived) notifications."""
    return sum(1 for item in notifications if not item.get("archived_at"))


def dismiss_notification(notifications: list, item_id: str) -> bool:
    """Mark one notification as archived. Returns False if not found or already archived."""
    item = find_notification(notifications, item_id)
    if item is None or item.get("archived_at"):
        return False
    item["archived_at"] = now_iso()
    return True


def dismiss_all_notifications(notifications: list) -> bool:
    """Archive all active notifications. Returns True if anything changed."""
    ts = now_iso()
    changed = False
    for item in notifications:
        if not item.get("archived_at"):
            item["archived_at"] = ts
            changed = True
    return changed


def mark_notification_opened(notifications: list, item_id: str) -> bool:
    """Mark as opened and archive (moves to History). Returns True if the item was found."""
    item = find_notification(notifications, item_id)
    if item is None:
        return False
    ts = now_iso()
    item["opened_at"] = ts
    if not item.get("read_at"):
        item["read_at"] = ts
    if not item.get("archived_at"):
        item["archived_at"] = ts
    return True


# ---------------------------------------------------------------------------
# Feed polling
# ---------------------------------------------------------------------------


class FeedPoller:
    """
    Fetches and parses a single feed URL.
    Stateless except for the shared HTTP session.
    Does NOT modify seen_items or the notification list — callers handle that.
    """

    def __init__(self, session: requests.Session, timeout: int = DEFAULT_REQUEST_TIMEOUT):
        self.session = session
        self.timeout = timeout

    def fetch(
        self,
        feed: dict,
        state: dict,
        seen_items: set,
        silent: bool = False,
    ) -> "tuple[list[str], list[dict], dict]":
        """
        Fetch a feed and process new entries.

        Returns:
            new_ids        — list of unseen entry IDs (caller adds to seen_items)
            new_notifs     — list of notification dicts (empty when silent=True)
            updated_state  — updated feed state dict

        Raises:
            requests.HTTPError / ValueError on fetch or parse failure.
        """
        headers: dict = {}
        if state.get("etag"):
            headers["If-None-Match"] = state["etag"]
        if state.get("last_modified"):
            headers["If-Modified-Since"] = state["last_modified"]

        response = self.session.get(feed["url"], timeout=self.timeout, headers=headers)

        if response.status_code == 304:
            state["last_success_at"] = now_iso()
            state["last_error"] = None
            return [], [], state

        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        if getattr(parsed, "bozo", False) and not parsed.entries:
            raise ValueError(str(getattr(parsed, "bozo_exception", "malformed feed")))

        state["etag"] = response.headers.get("ETag") or state.get("etag")
        state["last_modified"] = response.headers.get("Last-Modified") or state.get("last_modified")
        state["title"] = parsed.feed.get("title", feed.get("name", feed["url"]))
        state["last_success_at"] = now_iso()
        state["last_error"] = None

        new_ids: list = []
        new_notifs: list = []

        for entry in list(parsed.entries)[::-1]:
            item_id = entry_identifier(feed, entry)
            if item_id in seen_items:
                continue
            new_ids.append(item_id)
            if not silent:
                new_notifs.append(
                    {
                        "id": item_id,
                        "title": entry.get("title", "No title"),
                        "link": entry.get("link", ""),
                        "feed_title": parsed.feed.get("title", feed.get("name", "Unknown feed")),
                        "timestamp": entry_timestamp(entry),
                        "summary": preview_text(entry),
                        "created_at": now_iso(),
                        "opened_at": None,
                        "read_at": None,
                        "archived_at": None,
                    }
                )

        state["initialized"] = True
        return new_ids, new_notifs, state


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def entry_identifier(feed: dict, entry) -> str:
    return (
        entry.get("id")
        or entry.get("guid")
        or entry.get("link")
        or f"{feed.get('url', 'feed')}::{entry.get('title', 'untitled')}"
    )


def preview_text(entry) -> str:
    summary = entry.get("summary") or entry.get("description") or ""
    clean = re.sub(r"<[^>]+>", "", summary).strip()
    if not clean:
        return entry.get("link", "")
    if len(clean) <= 140:
        return clean
    return clean[:137].rstrip() + "..."


def entry_timestamp(entry) -> str:
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if published:
        try:
            return datetime.fromtimestamp(mktime(published)).strftime("%d-%m-%y %H:%M")
        except Exception:
            pass
    return datetime.now().strftime("%d-%m-%y %H:%M")


def display_title(item: dict, max_len: int = 64) -> str:
    title = item.get("title", "No title")
    if len(title) > max_len:
        title = title[: max_len - 3] + "..."
    timestamp = item.get("timestamp")
    return f"[{timestamp}] {title}" if timestamp else title


def feed_key(feed: dict) -> str:
    return feed.get("url", feed.get("name", "unknown-feed"))


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_iso_datetime(value) -> "datetime | None":
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
