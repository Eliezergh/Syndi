"""Tests for notification inbox management functions."""

from core import (
    active_notifications,
    dismiss_all_notifications,
    dismiss_notification,
    find_notification,
    mark_notification_opened,
    mark_notification_read,
    unread_count,
)


def make_notification(id, *, discarded=False, read=False, opened=False):
    return {
        "id": id,
        "title": f"Item {id}",
        "link": f"https://example.com/{id}",
        "discarded_at": "2025-01-01T00:00:00" if discarded else None,
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
    def test_excludes_dismissed(self):
        notifs = [
            make_notification("a"),
            make_notification("b", discarded=True),
            make_notification("c"),
        ]
        active = active_notifications(notifs)
        assert len(active) == 2
        assert all(not n.get("discarded_at") for n in active)

    def test_empty_list(self):
        assert active_notifications([]) == []

    def test_all_dismissed_returns_empty(self):
        notifs = [make_notification("a", discarded=True)]
        assert active_notifications(notifs) == []


class TestUnreadCount:
    def test_counts_active_and_unread(self):
        notifs = [
            make_notification("a"),  # unread, active
            make_notification("b", read=True),  # read, active
            make_notification("c", discarded=True),  # dismissed
            make_notification("d"),  # unread, active
        ]
        assert unread_count(notifs) == 2

    def test_zero_when_all_read(self):
        notifs = [make_notification("a", read=True), make_notification("b", read=True)]
        assert unread_count(notifs) == 0

    def test_zero_when_all_dismissed(self):
        notifs = [make_notification("a", discarded=True)]
        assert unread_count(notifs) == 0


class TestDismissNotification:
    def test_dismisses_active_item(self):
        notifs = [make_notification("a")]
        result = dismiss_notification(notifs, "a")
        assert result is True
        assert notifs[0]["discarded_at"] is not None

    def test_returns_false_if_already_dismissed(self):
        notifs = [make_notification("a", discarded=True)]
        assert dismiss_notification(notifs, "a") is False

    def test_returns_false_if_not_found(self):
        notifs = [make_notification("a")]
        assert dismiss_notification(notifs, "z") is False

    def test_does_not_affect_other_items(self):
        notifs = [make_notification("a"), make_notification("b")]
        dismiss_notification(notifs, "a")
        assert notifs[1]["discarded_at"] is None


class TestDismissAllNotifications:
    def test_dismisses_all_active(self):
        notifs = [make_notification("a"), make_notification("b"), make_notification("c")]
        result = dismiss_all_notifications(notifs)
        assert result is True
        assert all(n["discarded_at"] for n in notifs)

    def test_skips_already_dismissed(self):
        notifs = [make_notification("a", discarded=True)]
        result = dismiss_all_notifications(notifs)
        assert result is False  # nothing changed

    def test_mixed_state(self):
        notifs = [make_notification("a"), make_notification("b", discarded=True)]
        result = dismiss_all_notifications(notifs)
        assert result is True
        assert notifs[0]["discarded_at"] is not None


class TestMarkNotificationRead:
    def test_marks_unread_item(self):
        notifs = [make_notification("a")]
        result = mark_notification_read(notifs, "a")
        assert result is True
        assert notifs[0]["read_at"] is not None

    def test_idempotent_on_already_read(self):
        notifs = [make_notification("a", read=True)]
        result = mark_notification_read(notifs, "a")
        assert result is False  # nothing changed

    def test_does_not_dismiss(self):
        notifs = [make_notification("a")]
        mark_notification_read(notifs, "a")
        assert notifs[0]["discarded_at"] is None

    def test_returns_false_if_not_found(self):
        notifs = [make_notification("a")]
        assert mark_notification_read(notifs, "z") is False


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

    def test_does_not_overwrite_existing_read_at(self):
        notifs = [make_notification("a", read=True)]
        original_read = notifs[0]["read_at"]
        mark_notification_opened(notifs, "a")
        assert notifs[0]["read_at"] == original_read

    def test_returns_false_if_not_found(self):
        assert mark_notification_opened([], "any") is False
