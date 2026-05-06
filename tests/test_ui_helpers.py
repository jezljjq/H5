import unittest

from PyQt5.QtCore import QPoint

from h5bot.roi import auto_roi_from_match, format_roi
from h5bot.ui import _event_global_pos, _event_pos, _normalize_template_filename


class UiHelperTests(unittest.TestCase):
    def test_template_filename_preserves_supported_image_extensions(self):
        self.assertEqual(_normalize_template_filename("button.bmp"), "button.bmp")
        self.assertEqual(_normalize_template_filename("button.png"), "button.png")
        self.assertEqual(_normalize_template_filename("button.jpg"), "button.jpg")

    def test_template_filename_defaults_to_png_without_extension(self):
        self.assertEqual(_normalize_template_filename("button"), "button.png")

    def test_roi_formatter_uses_existing_flow_format(self):
        self.assertEqual(format_roi([1, 2, 30, 40]), "1,2,30,40")

    def test_auto_roi_expands_match_and_clamps_to_window(self):
        self.assertEqual(auto_roi_from_match(100, 200, 40, 20, 300, 260), [40, 170, 200, 250])
        self.assertEqual(auto_roi_from_match(10, 8, 12, 12, 100, 100), [0, 0, 52, 50])

    def test_mouse_event_helpers_support_pyqt5_events(self):
        event = FakePyQtMouseEvent()

        self.assertEqual(_event_pos(event), QPoint(10, 20))
        self.assertEqual(_event_global_pos(event), QPoint(30, 40))

    def test_mouse_event_helpers_support_pyside_style_events(self):
        event = FakePySideMouseEvent()

        self.assertEqual(_event_pos(event), QPoint(11, 21))
        self.assertEqual(_event_global_pos(event), QPoint(31, 41))


class FakePyQtMouseEvent:
    def pos(self):
        return QPoint(10, 20)

    def globalPos(self):
        return QPoint(30, 40)


class FakePySidePoint:
    def __init__(self, point):
        self.point = point

    def toPoint(self):
        return self.point


class FakePySideMouseEvent:
    def position(self):
        return FakePySidePoint(QPoint(11, 21))

    def globalPosition(self):
        return FakePySidePoint(QPoint(31, 41))


if __name__ == "__main__":
    unittest.main()
