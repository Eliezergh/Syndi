"""Tests for the notification-center action dispatcher (_handle_nc_action)."""

import sys
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Provide lightweight stubs for platform-only modules *before* importing syndi
# so the test suite can run on non-macOS CI environments.
# ---------------------------------------------------------------------------
rumps_mock = MagicMock()
rumps_mock.notifications = lambda f: f  # make @rumps.notifications a pass-through

sys.modules.setdefault("rumps", rumps_mock)
sys.modules.setdefault("AppKit", MagicMock())

from syndi import _handle_nc_action  # noqa: E402, I001


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app():
    """Return a minimal mock SyndiApp exposing the interface used by the handler."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHandleNcActionOpenUrl:
    """open_url action opens the link and marks the notification as read."""

    def test_opens_url_in_browser(self):
        payload = {"action": "open_url", "url": "https://example.com/1", "item_id": "id-1"}
        with patch("syndi.subprocess.run") as mock_run:
            _handle_nc_action(payload, _make_app())
        mock_run.assert_called_once_with(["open", "https://example.com/1"], check=False)

    def test_marks_notification_opened_when_item_id_present(self):
        app = _make_app()
        payload = {"action": "open_url", "url": "https://example.com/1", "item_id": "id-42"}
        with patch("syndi.subprocess.run"):
            _handle_nc_action(payload, app)
        app._handle_notification_opened.assert_called_once_with("id-42")

    def test_does_not_mark_when_item_id_absent(self):
        """Legacy payloads without item_id should not crash or try to mark."""
        app = _make_app()
        payload = {"action": "open_url", "url": "https://example.com/1"}
        with patch("syndi.subprocess.run"):
            _handle_nc_action(payload, app)
        app._handle_notification_opened.assert_not_called()

    def test_does_not_mark_when_app_is_none(self):
        """No crash if the app instance is not yet initialised."""
        payload = {"action": "open_url", "url": "https://example.com/1", "item_id": "id-1"}
        with patch("syndi.subprocess.run"):
            _handle_nc_action(payload, None)  # must not raise

    def test_skips_browser_for_non_http_url(self):
        """Unsafe URL schemes must never be passed to subprocess."""
        app = _make_app()
        payload = {"action": "open_url", "url": "file:///etc/passwd", "item_id": "id-1"}
        with patch("syndi.subprocess.run") as mock_run:
            _handle_nc_action(payload, app)
        mock_run.assert_not_called()

    def test_skips_browser_for_empty_url(self):
        app = _make_app()
        payload = {"action": "open_url", "url": "", "item_id": "id-1"}
        with patch("syndi.subprocess.run") as mock_run:
            _handle_nc_action(payload, app)
        mock_run.assert_not_called()


class TestHandleNcActionOpenFile:
    """open_file action opens the file and does not touch notifications."""

    def test_opens_file(self):
        payload = {"action": "open_file", "path": "/some/path/config.json"}
        with patch("syndi.subprocess.run") as mock_run:
            _handle_nc_action(payload, _make_app())
        mock_run.assert_called_once_with(["open", "/some/path/config.json"], check=False)

    def test_does_not_mark_notification(self):
        app = _make_app()
        payload = {"action": "open_file", "path": "/some/path/config.json"}
        with patch("syndi.subprocess.run"):
            _handle_nc_action(payload, app)
        app._handle_notification_opened.assert_not_called()

    def test_skips_open_when_path_absent(self):
        payload = {"action": "open_file"}
        with patch("syndi.subprocess.run") as mock_run:
            _handle_nc_action(payload, _make_app())
        mock_run.assert_not_called()


class TestHandleNcActionEdgeCases:
    """Edge-case payloads that must never crash the handler."""

    def test_unknown_action_does_nothing(self):
        app = _make_app()
        with patch("syndi.subprocess.run") as mock_run:
            _handle_nc_action({"action": "unknown_action"}, app)
        mock_run.assert_not_called()
        app._handle_notification_opened.assert_not_called()

    def test_empty_payload_does_nothing(self):
        app = _make_app()
        with patch("syndi.subprocess.run") as mock_run:
            _handle_nc_action({}, app)
        mock_run.assert_not_called()
        app._handle_notification_opened.assert_not_called()

    def test_none_app_with_open_file_does_not_crash(self):
        payload = {"action": "open_file", "path": "/some/path"}
        with patch("syndi.subprocess.run"):
            _handle_nc_action(payload, None)  # must not raise
