#!/usr/bin/env python3
"""
Syndi - Your simple syndication (RSS) notifier
A lightweight macOS menu bar app for RSS and status feed notifications
"""

import json
import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

import requests
import rumps

try:
    from AppKit import NSApplication, NSImage
except Exception:  # pragma: no cover - AppKit should exist on macOS runs
    NSApplication = None
    NSImage = None

import core
from core import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_CHECK_INTERVAL,
    DEFAULT_MAX_HISTORY_ITEMS,
    DEFAULT_MAX_STORED_NOTIFICATIONS,
    DEFAULT_MENU_NOTIFICATION_LIMIT,
    DEFAULT_REQUEST_TIMEOUT,
    USER_AGENT,
    FeedPoller,
)


def configure_logging(log_path: Path) -> logging.Logger:
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def resolve_resources_path():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.parent / "Resources"
    return Path(__file__).parent


class SyndiApp(rumps.App):
    def __init__(self):
        resources_path = resolve_resources_path()
        icon_path = resources_path / "media" / "menubar_icon.png"
        if not icon_path.exists():
            icon_path = resources_path / "menubar_icon.png"

        super(SyndiApp, self).__init__(
            name=APP_NAME,
            icon=str(icon_path) if icon_path.exists() else None,
            quit_button=None,
        )

        self.resources_path = resources_path

        syndi_folder = Path.home() / ".syndi"
        syndi_folder.mkdir(exist_ok=True)
        self.config_path = syndi_folder / "config.json"
        self.data_path = syndi_folder / "data.json"
        self.log_path = syndi_folder / "syndi.log"
        self.logger = configure_logging(self.log_path)

        app_icon_candidates = [
            self.resources_path / "media" / "syndi.png",
            self.resources_path / "syndi.png",
            self.resources_path / "media" / "menubar_icon.png",
            self.resources_path / "menubar_icon.png",
        ]
        self.app_icon_path = next(
            (str(path) for path in app_icon_candidates if path.exists()),
            None,
        )
        if NSApplication is not None and NSImage is not None and self.app_icon_path:
            image = NSImage.alloc().initWithContentsOfFile_(self.app_icon_path)
            if image is not None:
                NSApplication.sharedApplication().setApplicationIconImage_(image)
                self.logger.info("Application icon path resolved: %s", self.app_icon_path)

        default_config_path = self.resources_path / "config.json"
        if not self.config_path.exists() and default_config_path.exists():
            self.config_path.write_text(
                default_config_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            self.logger.info("Created default config at %s", self.config_path)

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.check_lock = Lock()
        self.is_checking = False

        self.raw_config: dict = {}
        self.feeds: list = []
        self.seen_items: set = set()
        self.notifications: list = []
        self.feed_state: dict = {}
        self.check_interval = DEFAULT_CHECK_INTERVAL
        self.last_check = None
        self.notification_enabled = True
        self.show_preview = True
        self.max_recent_items = DEFAULT_MAX_HISTORY_ITEMS
        self.max_stored_notifications = DEFAULT_MAX_STORED_NOTIFICATIONS
        self.menu_notification_limit = DEFAULT_MENU_NOTIFICATION_LIMIT
        self.request_timeout = DEFAULT_REQUEST_TIMEOUT
        self.startup_silent_sync = True

        cfg, config_err = core.load_config(self.config_path)
        self._apply_config(cfg)
        if config_err:
            self.logger.warning("Config load failed (%s); running on defaults", config_err)
            rumps.notification(
                title="Syndi",
                subtitle="Config load failed",
                message=f"Running on defaults. Check config.json. ({type(config_err).__name__})",
            )
        self._load_data()
        self.poller = FeedPoller(self.session, self.request_timeout)
        self.build_menu()

        self.timer = rumps.Timer(self.feeds_bg_checker, self.check_interval)
        self.timer.start()

    def build_menu(self):
        self.menu.clear()
        self.menu.add(rumps.MenuItem("Check now", callback=self.feeds_bg_checker))

        if self.is_checking:
            self.menu.add(rumps.MenuItem("Checking feeds…"))
        elif self.last_check:
            self.menu.add(rumps.MenuItem(f"Last check: {self.last_check.strftime('%H:%M:%S')}"))
        else:
            self.menu.add(rumps.MenuItem("Last check: Never"))

        self.menu.add(rumps.separator)
        self.menu.add(self._build_notifications_menu())
        self.menu.add(self._build_history_menu())
        self.menu.add(self._build_feeds_menu())

        options_menu = rumps.MenuItem("Options")
        options_menu.add(rumps.MenuItem("Preferences…", callback=self.open_preferences))
        options_menu.add(rumps.separator)
        options_menu.add(rumps.MenuItem("Test notification", callback=self.test_notification))
        options_menu.add(rumps.MenuItem("Open config", callback=self.open_config))
        options_menu.add(rumps.MenuItem("Open log", callback=self.open_log))
        options_menu.add(rumps.MenuItem("Reload config", callback=self.reload_config))
        options_menu.add(rumps.separator)
        options_menu.add(
            rumps.MenuItem(
                "Dismiss all notifications",
                callback=self.dismiss_all_notifications,
            )
        )
        options_menu.add(rumps.MenuItem("Clear seen data", callback=self.clear_seen_data))
        self.menu.add(options_menu)

        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("About Syndi", callback=self.show_about))
        self.menu.add(rumps.MenuItem("Quit Syndi", callback=self.quit_app))

    def _build_notifications_menu(self):
        active = core.active_notifications(self.notifications)
        label = f"Notifications ({len(active)})"
        menu = rumps.MenuItem(label)

        if not active:
            menu.add(rumps.MenuItem("No active notifications"))
            return menu

        for item in active[: self.menu_notification_limit]:
            title = core.display_title(item)
            row = rumps.MenuItem(title)
            row.add(
                rumps.MenuItem(
                    "Open link",
                    callback=lambda s, iid=item["id"]: self._action_open(iid),
                )
            )
            row.add(
                rumps.MenuItem(
                    "Dismiss",
                    callback=lambda s, iid=item["id"]: self._action_dismiss(iid),
                )
            )
            menu.add(row)

        overflow = len(active) - self.menu_notification_limit
        if overflow > 0:
            menu.add(rumps.MenuItem(f"+ {overflow} more"))

        menu.add(rumps.separator)
        menu.add(rumps.MenuItem("Dismiss all", callback=self.dismiss_all_notifications))
        return menu

    def _build_history_menu(self):
        menu = rumps.MenuItem("History")
        if not self.notifications:
            menu.add(rumps.MenuItem("No history yet"))
            return menu

        for item in self.notifications[: self.max_recent_items]:
            label = core.display_title(item)
            if item.get("archived_at"):
                label = f"[archived] {label}"
            menu.add(
                rumps.MenuItem(
                    label,
                    callback=lambda s, iid=item["id"]: self._action_open(iid),
                )
            )
        return menu

    def _build_feeds_menu(self):
        menu = rumps.MenuItem("Feeds")
        if not self.feeds:
            menu.add(rumps.MenuItem("No feeds configured"))
            return menu

        for feed in self.feeds:
            fk = core.feed_key(feed)
            state = self.feed_state.get(fk, {})
            name = feed.get("name", feed.get("url", "Unnamed feed"))
            if not feed.get("enabled", True):
                label = f"{name}: Disabled"
            elif state.get("last_error"):
                label = f"⚠ {name}: Error"
            elif state.get("last_success_at"):
                ts = core.parse_iso_datetime(state["last_success_at"])
                time_str = ts.strftime("%H:%M") if ts else ""
                label = f"{name}: OK {time_str}"
            elif state.get("initialized"):
                label = f"{name}: Ready"
            else:
                label = f"{name}: Pending first sync"
            menu.add(rumps.MenuItem(label))
        return menu

    def open_preferences(self, sender):
        from preferences import show_preferences

        self.dialog_to_front()

        icon_path = self.app_icon_path
        if icon_path:
            self.logger.info("Preferences icon path resolved: %s", icon_path)
        else:
            self.logger.warning(
                "Preferences icon path not found in resources; using default alert icon"
            )

        def on_save(updated: dict):
            core.save_config(self.config_path, updated)
            self.reload_config(None)

        show_preferences(self.raw_config, on_save, icon_path=icon_path)

    def _action_open(self, item_id: str):
        with self.check_lock:
            opened = core.mark_notification_opened(self.notifications, item_id)
            item = core.find_notification(self.notifications, item_id) if opened else None
            if opened:
                self._persist_and_rebuild()
        if item:
            self.open_url(item.get("link"))

    def _action_dismiss(self, item_id: str):
        with self.check_lock:
            if core.dismiss_notification(self.notifications, item_id):
                self._persist_and_rebuild()

    def test_notification(self, sender):
        ts = datetime.now().strftime("%H:%M:%S")
        self.send_notification(
            APP_NAME,
            "Test Notification",
            f"{ts} — This is a test notification from Syndi.",
            {"action": "open_file", "path": str(self.config_path)},
        )

    def open_config(self, sender):
        if shutil.which("code"):
            subprocess.run(["code", str(self.config_path)], check=False)
        else:
            subprocess.run(["open", str(self.config_path)], check=False)

    def open_log(self, sender):
        subprocess.run(["open", str(self.log_path)], check=False)

    def reload_config(self, sender):
        cfg, err = core.load_config(self.config_path)
        if err:
            self.logger.error("Failed to reload config: %s", err)
            rumps.alert("Config Error", f"Could not reload config:\n{err}")
            return
        self._apply_config(cfg)
        self.poller = FeedPoller(self.session, self.request_timeout)
        self.notifications = core.trim_notifications(
            self.notifications,
            self.max_stored_notifications,
        )
        self.timer.stop()
        self.timer = rumps.Timer(self.feeds_bg_checker, self.check_interval)
        self.timer.start()
        self._persist_and_rebuild()
        self.send_notification(APP_NAME, "Configuration Reloaded", "Settings applied.")

    def clear_seen_data(self, sender):
        self.dialog_to_front()
        response = rumps.alert(
            title="Clear Seen Data",
            message=(
                f"Are you sure you want to clear all {len(self.seen_items)} seen items and "
                f"{len(self.notifications)} stored notifications?\n\n"
                "Existing feed items will be used to rebuild the silent baseline on the "
                "next successful check."
            ),
            ok="Clear",
            cancel="Cancel",
        )

        if response == 1:
            self.seen_items = set()
            self.notifications = []
            self.feed_state = {}
            self._persist_and_rebuild()
            self.send_notification(APP_NAME, "Data Cleared", "State and notifications cleared.")

    def dismiss_all_notifications(self, sender=None):
        with self.check_lock:
            if core.dismiss_all_notifications(self.notifications):
                self._persist_and_rebuild()

    def show_about(self, sender):
        self.dialog_to_front()
        active = len(core.active_notifications(self.notifications))
        enabled = len([f for f in self.feeds if f.get("enabled", True)])
        rumps.alert(
            title="About Syndi",
            message=(
                f"Syndi — Your simple syndication notifier\n\n"
                f"Version {APP_VERSION}\n"
                f"Monitoring {enabled} enabled feed(s)\n"
                f"Active notifications: {active}\n"
                f"Check interval: {self.check_interval}s\n\n"
                "Developed by EliezerGH\n"
                "https://github.com/Eliezergh"
            ),
        )

    def quit_app(self, sender):
        self.session.close()
        rumps.quit_application()

    def _apply_config(self, cfg: core.SyndiConfig):
        self.feeds = cfg.feeds
        self.check_interval = cfg.check_interval
        self.notification_enabled = cfg.notification_enabled
        self.show_preview = cfg.show_preview
        self.max_recent_items = cfg.max_recent_items
        self.max_stored_notifications = cfg.max_stored_notifications
        self.menu_notification_limit = cfg.menu_notification_limit
        self.request_timeout = cfg.request_timeout
        self.startup_silent_sync = cfg.startup_silent_sync
        # Use the raw dict from disk so unknown keys (e.g. future fields) are
        # preserved when the user saves from Preferences.  Fall back to the
        # normalised dict if the file isn't readable at this point.
        try:
            self.raw_config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            self.raw_config = cfg.to_dict()

    def _load_data(self):
        try:
            seen, notifications, feed_state, last_check = core.load_data(
                self.data_path, self.max_stored_notifications
            )
            self.seen_items = seen
            self.notifications = notifications
            self.feed_state = feed_state
            self.last_check = last_check
            self.logger.info(
                "Loaded %s seen items and %s notifications",
                len(self.seen_items),
                len(self.notifications),
            )
        except Exception:
            self.logger.exception("Error loading data")
            self.seen_items = set()
            self.notifications = []
            self.feed_state = {}

    def _persist_and_rebuild(self):
        try:
            core.save_data(
                self.data_path,
                self.seen_items,
                self.notifications,
                self.feed_state,
                self.last_check,
                self.max_stored_notifications,
            )
        except Exception:
            self.logger.exception("Error saving data")
        self.build_menu()

    def feeds_bg_checker(self, sender=None):
        if not self.feeds:
            return

        if not self.check_lock.acquire(blocking=False):
            self.logger.info("Skipping feed check because another check is already running")
            return

        self.is_checking = True
        self.last_check = datetime.now()
        self.build_menu()

        try:
            new_total = 0
            for feed in self.feeds:
                if not feed.get("enabled", True):
                    continue
                new_total += self._poll_feed(feed)

            if new_total:
                self.logger.info("Detected %s new item(s)", new_total)
        finally:
            self.is_checking = False
            self._persist_and_rebuild()
            self.check_lock.release()

    def _poll_feed(self, feed: dict) -> int:
        fk = core.feed_key(feed)
        state = self.feed_state.setdefault(fk, {})
        silent = self.startup_silent_sync and not state.get("initialized", False)
        try:
            new_ids, new_notifs, updated_state = self.poller.fetch(
                feed, state, self.seen_items, silent=silent
            )
            self.seen_items.update(new_ids)
            self.feed_state[fk] = updated_state

            for notif in new_notifs:
                self.notifications.insert(0, notif)
                if self.notification_enabled:
                    message = notif["summary"] if self.show_preview else notif["link"]
                    self.send_notification(
                        feed.get("name", notif["feed_title"]),
                        notif["title"],
                        message,
                        {"action": "open_url", "url": notif["link"], "item_id": notif["id"]},
                    )

            self.notifications = core.trim_notifications(
                self.notifications, self.max_stored_notifications
            )
            return len(new_notifs)
        except Exception as exc:
            state["last_error"] = str(exc)
            self.logger.exception("Error fetching feed %s", feed.get("url"))
            return 0

    def send_notification(self, title: str, subtitle: str = "", message: str = "", data=None):
        try:
            rumps.notification(title, subtitle, message, data=data)
        except Exception:
            self.logger.exception("Failed to send notification")

    def open_url(self, url: str):
        if url and urlparse(url).scheme in ("http", "https"):
            subprocess.run(["open", url], check=False)

    def dialog_to_front(self):
        if getattr(sys, "frozen", False):
            app_name = APP_NAME
        else:
            app_name = "Python"
        script = (
            'tell application "System Events" to set frontmost of '
            f'(first process whose name contains "{app_name}") to true'
        )
        subprocess.run(["osascript", "-e", script], check=False, capture_output=True)


@rumps.notifications
def notification_center(notification):
    payload = notification.data or {}
    action = payload.get("action")
    if action == "open_url":
        url = payload.get("url", "")
        if urlparse(url).scheme in ("http", "https"):
            subprocess.run(["open", url], check=False)
    elif action == "open_file":
        path = payload.get("path")
        if path:
            subprocess.run(["open", path], check=False)


def main():
    SyndiApp().run()


if __name__ == "__main__":
    main()
