"""Tests for load_data, save_data, and trim_notifications."""

import json
from datetime import datetime

from core import load_data, save_data, trim_notifications


class TestLoadData:
    def test_missing_file_returns_empty_state(self, data_path):
        seen, notifs, state, last = load_data(data_path, 500)
        assert seen == set()
        assert notifs == []
        assert state == {}
        assert last is None

    def test_reload_after_save(self, data_path):
        seen = {"id1", "id2"}
        notifs = [
            {
                "id": "id1",
                "title": "Test",
                "link": "https://example.com",
                "feed_title": "Feed",
                "timestamp": "",
                "summary": "",
                "created_at": "2025-01-01T00:00:00",
                "opened_at": None,
                "read_at": None,
                "archived_at": None,
            }
        ]
        feed_state = {"https://example.com/rss": {"initialized": True}}
        last_check = datetime(2025, 5, 1, 10, 0, 0)

        save_data(data_path, seen, notifs, feed_state, last_check, 500)
        loaded_seen, loaded_notifs, loaded_state, loaded_lc = load_data(data_path, 500)

        assert loaded_seen == seen
        assert loaded_notifs[0]["title"] == "Test"
        assert loaded_state == feed_state
        assert loaded_lc == last_check

    def test_written_json_is_valid(self, data_path):
        save_data(data_path, set(), [], {}, None, 500)
        raw = json.loads(data_path.read_text())
        assert "seen_items" in raw
        assert "notifications" in raw

    def test_legacy_migration_recent_items(self, data_path):
        legacy = {
            "seen_items": ["old-id"],
            "recent_items": [
                {
                    "title": "Old Article",
                    "link": "https://example.com/old",
                    "feed_title": "Old Feed",
                    "timestamp": "01-05-25 10:00",
                }
            ],
        }
        data_path.write_text(json.dumps(legacy), encoding="utf-8")
        seen, notifs, _, _ = load_data(data_path, 500)

        assert "old-id" in seen
        assert len(notifs) == 1
        assert notifs[0]["title"] == "Old Article"
        assert notifs[0]["read_at"] is None
        assert notifs[0]["archived_at"] is None

    def test_last_check_roundtrip(self, data_path):
        ts = datetime(2025, 6, 15, 12, 30, 0)
        save_data(data_path, set(), [], {}, ts, 500)
        _, _, _, loaded_lc = load_data(data_path, 500)
        assert loaded_lc == ts

    def test_trims_on_load(self, data_path):
        notifs = [{"id": str(i), "archived_at": "2025-01-01T00:00:00"} for i in range(20)]
        save_data(data_path, set(), notifs, {}, None, 20)
        _, loaded, _, _ = load_data(data_path, 5)
        assert len(loaded) == 5


class TestTrimNotifications:
    def test_no_trim_when_under_limit(self):
        notifs = [{"id": str(i), "archived_at": None} for i in range(5)]
        result = trim_notifications(notifs, 10)
        assert len(result) == 5

    def test_drops_old_archived_first(self):
        notifs = [
            {"id": "active-1", "archived_at": None},
            {"id": "archived-1", "archived_at": "2025-01-01T00:00:00"},
            {"id": "active-2", "archived_at": None},
            {"id": "archived-2", "archived_at": "2025-01-01T00:00:00"},
        ]
        result = trim_notifications(notifs, max_stored=2)
        result_ids = {n["id"] for n in result}
        # Active ones must be kept
        assert "active-1" in result_ids
        assert "active-2" in result_ids

    def test_exact_limit_not_trimmed(self):
        notifs = [{"id": str(i), "archived_at": None} for i in range(10)]
        assert len(trim_notifications(notifs, 10)) == 10

    def test_returns_new_list_when_trimming(self):
        notifs = [
            {
                "id": str(i),
                "archived_at": "2025-01-01T00:00:00",
            }
            for i in range(10)
        ]
        result = trim_notifications(notifs, max_stored=5)
        assert result is not notifs
        assert len(result) == 5

    def test_hard_cap_enforced_even_with_all_active(self):
        # All items are active (no archived_at); cap must still be honoured
        notifs = [{"id": str(i), "archived_at": None} for i in range(20)]
        result = trim_notifications(notifs, max_stored=10)
        assert len(result) == 10

    def test_active_items_kept_over_archived(self):
        # When cap forces a choice, active items survive and archived are dropped
        active = [{"id": f"a{i}", "archived_at": None} for i in range(8)]
        archived = [{"id": f"d{i}", "archived_at": "2025-01-01T00:00:00"} for i in range(8)]
        result = trim_notifications(active + archived, max_stored=8)
        result_ids = {n["id"] for n in result}
        assert all(n["id"] in result_ids for n in active)
        assert not any(n["id"] in result_ids for n in archived)
