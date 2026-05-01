"""
Syndi — Preferences window using AppKit/PyObjC.

Displays a native macOS modal dialog for editing Syndi settings.
The caller provides the current raw config dict and an on_save callback.
All feed-list management is done via config.json directly.
"""

from AppKit import (
    NSAlert,
    NSButton,
    NSFont,
    NSImage,
    NSTextField,
    NSView,
)
from Foundation import NSMakeRect

# Layout constants (AppKit uses bottom-left origin)
_W = 370
_H = 380
_LX = 15  # label x
_LW = 200  # label width
_IX = 220  # input x
_IW = 135  # input width
_RH = 24  # row height (text field)
_CH = 22  # checkbox height
_PAD = 8  # row padding
_SEC = 18  # extra gap above section headers

# NSAlert button return values
_SAVE_RETURN = 1000


def _label(text: str, x: float, y: float, width: float = _LW, height: float = _RH) -> NSTextField:
    field = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, width, height))
    field.setStringValue_(text)
    field.setBezeled_(False)
    field.setDrawsBackground_(False)
    field.setEditable_(False)
    field.setSelectable_(False)
    return field


def _input(value, x: float, y: float, width: float = _IW, height: float = _RH) -> NSTextField:
    field = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, width, height))
    field.setStringValue_(str(value))
    return field


def _checkbox(title: str, checked: bool, x: float, y: float, width: float = _W - 30) -> NSButton:
    btn = NSButton.alloc().initWithFrame_(NSMakeRect(x, y, width, _CH))
    btn.setButtonType_(3)  # NSButtonTypeSwitch = 3
    btn.setTitle_(title)
    btn.setState_(1 if checked else 0)
    return btn


def _section_header(text: str, x: float, y: float, width: float = _W - 30) -> NSTextField:
    field = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, width, 18))
    field.setStringValue_(text)
    field.setBezeled_(False)
    field.setDrawsBackground_(False)
    field.setEditable_(False)
    field.setSelectable_(False)
    field.setFont_(NSFont.boldSystemFontOfSize_(11.0))
    return field


def _safe_int(ns_field: NSTextField, fallback: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(str(ns_field.stringValue())))
    except (ValueError, AttributeError):
        return fallback


def show_preferences(config: dict, on_save, icon_path: str | None = None) -> None:
    """
    Display the Preferences modal dialog.

    Args:
        config:   The current raw config dict (from config.json).
        on_save:  Callable(updated_config_dict).  Called only when the user
                  clicks Save.  The dict is a copy of config with form fields
                  overwritten; keys not shown in the form (e.g. 'feeds') are
                  preserved unchanged.
    """
    alert = NSAlert.alloc().init()
    alert.setMessageText_("Syndi Preferences")
    alert.setInformativeText_("Changes are written to config.json and applied immediately.")
    alert.addButtonWithTitle_("Save")
    alert.addButtonWithTitle_("Cancel")

    if icon_path:
        image = NSImage.alloc().initWithContentsOfFile_(icon_path)
        if image is not None:
            alert.setIcon_(image)

    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, _W, _H))

    # Build rows bottom-up (AppKit y=0 is bottom)
    y = _H - 28

    # ── Polling ──────────────────────────────────────────────────────────
    view.addSubview_(_section_header("Polling", _LX, y))
    y -= _SEC + 10

    view.addSubview_(_label("Check interval (seconds):", _LX, y + 2))
    f_interval = _input(config.get("check_interval_seconds", 300), _IX, y)
    view.addSubview_(f_interval)
    y -= _RH + _PAD

    view.addSubview_(_label("Request timeout (seconds):", _LX, y + 2))
    f_timeout = _input(config.get("request_timeout_seconds", 10), _IX, y)
    view.addSubview_(f_timeout)
    y -= _RH + _PAD + _SEC

    # ── Notifications ────────────────────────────────────────────────────
    view.addSubview_(_section_header("Notifications", _LX, y))
    y -= _SEC + 6

    cb_enabled = _checkbox(
        "Enable system notifications",
        config.get("notification_enabled", True),
        _LX,
        y,
    )
    view.addSubview_(cb_enabled)
    y -= _CH + _PAD

    cb_preview = _checkbox(
        "Show content preview in notifications",
        config.get("show_preview", True),
        _LX,
        y,
    )
    view.addSubview_(cb_preview)
    y -= _CH + _PAD

    cb_silent = _checkbox(
        "Silent sync on first fetch of each feed",
        config.get("startup_silent_sync", True),
        _LX,
        y,
    )
    view.addSubview_(cb_silent)
    y -= _CH + _PAD + _SEC

    # ── Display ──────────────────────────────────────────────────────────
    view.addSubview_(_section_header("Display", _LX, y))
    y -= _SEC + 10

    view.addSubview_(_label("Max notifications in menu:", _LX, y + 2))
    f_menu_limit = _input(config.get("max_menu_notifications", 12), _IX, y)
    view.addSubview_(f_menu_limit)
    y -= _RH + _PAD

    view.addSubview_(_label("Max history items:", _LX, y + 2))
    f_max_history = _input(config.get("max_recent_items", 50), _IX, y)
    view.addSubview_(f_max_history)

    alert.setAccessoryView_(view)
    response = alert.runModal()

    if response != _SAVE_RETURN:
        return

    updated = dict(config)
    updated["check_interval_seconds"] = _safe_int(f_interval, 300, minimum=30)
    updated["request_timeout_seconds"] = _safe_int(f_timeout, 10, minimum=3)
    updated["notification_enabled"] = bool(cb_enabled.state())
    updated["show_preview"] = bool(cb_preview.state())
    updated["startup_silent_sync"] = bool(cb_silent.state())
    updated["max_menu_notifications"] = _safe_int(f_menu_limit, 12, minimum=5)
    updated["max_recent_items"] = _safe_int(f_max_history, 50, minimum=10)

    on_save(updated)
