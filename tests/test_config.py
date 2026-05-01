"""Tests for SyndiConfig, load_config, and save_config."""

import json

from core import (
    DEFAULT_CHECK_INTERVAL,
    DEFAULT_MAX_HISTORY_ITEMS,
    DEFAULT_MAX_STORED_NOTIFICATIONS,
    DEFAULT_MENU_NOTIFICATION_LIMIT,
    DEFAULT_REQUEST_TIMEOUT,
    SyndiConfig,
    load_config,
    save_config,
)


class TestSyndiConfigFromDict:
    def test_defaults_when_empty_dict(self):
        cfg = SyndiConfig.from_dict({})
        assert cfg.check_interval == DEFAULT_CHECK_INTERVAL
        assert cfg.notification_enabled is True
        assert cfg.show_preview is True
        assert cfg.startup_silent_sync is True
        assert cfg.max_recent_items == DEFAULT_MAX_HISTORY_ITEMS
        assert cfg.max_stored_notifications == DEFAULT_MAX_STORED_NOTIFICATIONS
        assert cfg.request_timeout == DEFAULT_REQUEST_TIMEOUT
        assert cfg.menu_notification_limit == DEFAULT_MENU_NOTIFICATION_LIMIT
        assert cfg.feeds == []

    def test_custom_values(self):
        cfg = SyndiConfig.from_dict(
            {
                "check_interval_seconds": 60,
                "notification_enabled": False,
                "show_preview": False,
                "max_recent_items": 20,
                "startup_silent_sync": False,
            }
        )
        assert cfg.check_interval == 60
        assert cfg.notification_enabled is False
        assert cfg.show_preview is False
        assert cfg.max_recent_items == 20
        assert cfg.startup_silent_sync is False

    def test_clamps_check_interval_minimum(self):
        cfg = SyndiConfig.from_dict({"check_interval_seconds": 0})
        assert cfg.check_interval == 30

    def test_clamps_request_timeout_minimum(self):
        cfg = SyndiConfig.from_dict({"request_timeout_seconds": 1})
        assert cfg.request_timeout == 3

    def test_clamps_max_recent_items_minimum(self):
        cfg = SyndiConfig.from_dict({"max_recent_items": 2})
        assert cfg.max_recent_items == 10

    def test_clamps_menu_notification_limit_minimum(self):
        cfg = SyndiConfig.from_dict({"max_menu_notifications": 1})
        assert cfg.menu_notification_limit == 5

    def test_max_stored_at_least_max_recent(self):
        # max_stored < max_recent should be clamped up to max_recent
        cfg = SyndiConfig.from_dict({"max_recent_items": 100, "max_stored_notifications": 50})
        assert cfg.max_stored_notifications >= cfg.max_recent_items

    def test_feeds_preserved(self):
        feeds = [{"name": "HN", "url": "https://news.ycombinator.com/rss", "enabled": True}]
        cfg = SyndiConfig.from_dict({"feeds": feeds})
        assert cfg.feeds == feeds


class TestSyndiConfigToDict:
    def test_round_trip(self):
        original = {
            "check_interval_seconds": 120,
            "notification_enabled": False,
            "max_recent_items": 25,
        }
        d = SyndiConfig.from_dict(original).to_dict()
        assert d["check_interval_seconds"] == 120
        assert d["notification_enabled"] is False
        assert d["max_recent_items"] == 25

    def test_all_required_keys_present(self):
        d = SyndiConfig().to_dict()
        required = {
            "feeds",
            "check_interval_seconds",
            "notification_enabled",
            "show_preview",
            "max_recent_items",
            "max_stored_notifications",
            "max_menu_notifications",
            "request_timeout_seconds",
            "startup_silent_sync",
        }
        assert required.issubset(d.keys())


class TestLoadConfig:
    def test_reads_file_correctly(self, config_file):
        cfg, err = load_config(config_file)
        assert err is None
        assert cfg.check_interval == 300
        assert len(cfg.feeds) == 1

    def test_missing_file_returns_defaults_and_error(self, tmp_path):
        cfg, err = load_config(tmp_path / "nonexistent.json")
        assert err is not None
        assert cfg.check_interval == DEFAULT_CHECK_INTERVAL

    def test_malformed_json_returns_error(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("{not valid json}", encoding="utf-8")
        cfg, err = load_config(path)
        assert err is not None


class TestSaveConfig:
    def test_writes_readable_json(self, tmp_path):
        path = tmp_path / "config.json"
        cfg = SyndiConfig.from_dict({"check_interval_seconds": 60})
        save_config(path, cfg.to_dict())
        data = json.loads(path.read_text())
        assert data["check_interval_seconds"] == 60

    def test_atomic_write_produces_valid_json(self, tmp_path):
        path = tmp_path / "config.json"
        save_config(path, SyndiConfig().to_dict())
        json.loads(path.read_text())  # should not raise

    def test_preserves_feeds_key(self, tmp_path):
        path = tmp_path / "config.json"
        raw = SyndiConfig().to_dict()
        raw["feeds"] = [{"name": "Test", "url": "https://example.com/rss"}]
        save_config(path, raw)
        assert json.loads(path.read_text())["feeds"][0]["name"] == "Test"
