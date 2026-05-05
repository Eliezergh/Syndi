"""Tests for notification inbox management functions."""

from core import (
    active_notifications,
    dismiss_all_notifications,
    dismiss_notification,
    find_notification,
    mark_notification_opened,
    unread_count,
)


def make_notification(id, *, discarded=False, read=False, opened=False):
    return {
        "id": id,
        "title": f"Item {id}",
        "link": f"https://example.com/{id}",
        "archived_at": "2025-01-01T00:00:00" if discarded else None,
        "read_at": "2025-01-01T00:00:00" if read else None,
        "opened_at": "2025-01-01T00:00:00" if opened else None,
    }


class TestFindNotification:
    def test_finds_by_id(self):
        notifs = [make_notification("a"), make_notification("b")]
        assert find_notification(notifs, "a")["id"] == "a"

    def test_returns_none_if_not_found(self):
        notifs = [make_notification("a")]
        assert find_notification(notifs, "z") is None

    def test_empty_list(self):
        assert find_notification([], "any") is None


class TestActiveNotifications:
    def test_excludes_archived(self):
        notifs = [
            make_notification("a"),
            make_notification("b", discarded=True),
            make_notification("c"),
        ]
        active = active_notifications(notifs)
        assert len(active) == 2
        assert all(not n.get("archived_at") for n in active)

    def test_empty_list(self):
        assert active_notifications([]) == []

    def test_all_archived_returns_empty(self):
        notifs = [make_notification("a", discarded=True)]
        assert active_notifications(notifs) == []


class TestUnreadCount:
    def test_counts_active_notifications(self):
        notifs = [
            make_notification("a"),  # active
            make_notification("b"),  # active
            make_notification("c", discarded=True),  # archived
        ]
        assert unread_count(notifs) == 2

    def test_zero_when_all_archived(self):
        notifs = [make_notification("a", discarded=True)]
        assert unread_count(notifs) == 0

    def test_zero_for_empty_list(self):
        assert unread_count([]) == 0


class TestDismissNotification:
    def test_archives_active_item(self):
        notifs = [make_notification("a")]
        result = dismiss_notification(notifs, "a")
        assert result is True
        assert notifs[0]["archived_at"] is not None

    def test_returns_false_if_already_archived(self):
        notifs = [make_notification("a", discarded=True)]
        assert dismiss_notification(notifs, "a") is False

    def test_returns_false_if_not_found(self):
        notifs = [make_notification("a")]
        assert dismiss_notification(notifs, "z") is False

    def test_does_not_affect_other_items(self):
        notifs = [make_notification("a"), make_notification("b")]
        dismiss_notification(notifs, "a")
        assert notifs[1]["archived_at"] is None


class TestDismissAllNotifications:
    def test_archives_all_active(self):
        notifs = [make_notification("a"), make_notification("b"), make_notification("c")]
        result = dismiss_all_notifications(notifs)
        assert result is True
        assert all(n["archived_at"] for n in notifs)

    def test_skips_already_archived(self):
        notifs = [make_notification("a", discarded=True)]
        result = dismiss_all_notifications(notifs)
        assert result is False  # nothing changed

    def test_mixed_state(self):
        notifs = [make_notification("a"), make_notification("b", discarded=True)]
        result = dismiss_all_notifications(notifs)
        assert result is True
        assert notifs[0]["archived_at"] is not None


class TestMarkNotificationOpened:
    def test_sets_opened_at(self):
        notifs = [make_notification("a")]
        result = mark_notification_opened(notifs, "a")
        assert result is True
        assert notifs[0]["opened_at"] is not None

    def test_also_sets_read_at(self):
        notifs = [make_notification("a")]
        mark_notification_opened(notifs, "a")
        assert notifs[0]["read_at"] is not None

    def test_also_archives_notification(self):
        notifs = [make_notification("a")]
        mark_notification_opened(notifs, "a")
        assert notifs[0]["archived_at"] is not None

    def test_not_in_active_after_opening(self):
        notifs = [make_notification("a")]
        mark_notification_opened(notifs, "a")
        assert active_notifications(notifs) == []

    def test_does_not_overwrite_existing_read_at(self):
        notifs = [make_notification("a", read=True)]
        original_read = notifs[0]["read_at"]
        mark_notification_opened(notifs, "a")
        assert notifs[0]["read_at"] == original_read

    def test_returns_false_if_not_found(self):
        assert mark_notification_opened([], "any") is False
