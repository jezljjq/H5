import unittest
import sys

# --- Lazy imports — h5bot.ui depends on PyQt5 which is Windows-only ---
# We stub the import at module level so unittest discovery doesn't crash.

try:
    from PyQt5.QtCore import QPoint as _QPoint
    QPoint = _QPoint
    _HAS_PYQT5 = True
except ImportError:
    QPoint = None
    _HAS_PYQT5 = False


def _ui():
    """Lazy-import h5bot.ui helpers (may fail on headless/CI)."""
    from h5bot.roi import auto_roi_from_match, format_roi
    from h5bot.ui import _event_global_pos, _event_pos, _normalize_template_filename
    return auto_roi_from_match, format_roi, _event_global_pos, _event_pos, _normalize_template_filename


@unittest.skipIf(not _HAS_PYQT5, "需要 PyQt5（仅 Windows GUI 环境）")
class UiHelperTests(unittest.TestCase):
    """PyQt5-dependent test cases for UI helper functions."""

    def _import(self):
        return _ui()

    def test_template_filename_preserves_supported_image_extensions(self):
        *_, fn = self._import()
        assert fn("button.bmp") == "button.bmp"
        assert fn("button.png") == "button.png"
        assert fn("button.jpg") == "button.jpg"

    def test_template_filename_defaults_to_png_without_extension(self):
        *_, fn = self._import()
        assert fn("button") == "button.png"

    def test_roi_formatter_uses_existing_flow_format(self):
        _, fmt, *_ = self._import()
        assert fmt([1, 2, 30, 40]) == "1,2,30,40"

    def test_auto_roi_expands_match_and_clamps_to_window(self):
        auto, *_ = self._import()
        assert auto(100, 200, 40, 20, 300, 260) == [40, 170, 200, 250]
        assert auto(10, 8, 12, 12, 100, 100) == [0, 0, 52, 50]

    def test_mouse_event_helpers_support_pyqt5_events(self):
        *_, ep, egp = self._import()
        evt = _FakePyQtMouseEvent()
        assert ep(evt) == QPoint(10, 20)
        assert egp(evt) == QPoint(30, 40)

    def test_mouse_event_helpers_support_pyside_style_events(self):
        *_, ep, egp = self._import()
        evt = _FakePySideMouseEvent()
     