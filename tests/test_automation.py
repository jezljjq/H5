import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from h5bot.automation import GameWindow, Win32Automation, _bitblt_failed
from h5bot.dm_clicker import DmFindResult


class FakeWin32Gui:
    def __init__(self):
        self.calls = []

    def WindowFromPoint(self, point):
        self.calls.append(("WindowFromPoint", point))
        return 20

    def GetAncestor(self, hwnd, flag):
        self.calls.append(("GetAncestor", hwnd, flag))
        return 10

    def IsWindow(self, hwnd):
        return hwnd == 10

    def GetWindowText(self, hwnd):
        return "斗罗大陆H5"

    def ClientToScreen(self, hwnd, point):
        self.calls.append(("ClientToScreen", hwnd, point))
        return point[0] + 100, point[1] + 200

    def ScreenToClient(self, hwnd, point):
        self.calls.append(("ScreenToClient", hwnd, point))
        return point[0] - 100, point[1] - 200

    def ShowWindow(self, hwnd, command):
        self.calls.append(("ShowWindow", hwnd, command))

    def SetForegroundWindow(self, hwnd):
        self.calls.append(("SetForegroundWindow", hwnd))


class FakeWin32Con:
    GA_ROOT = 2
    SW_RESTORE = 9
    WM_MOUSEMOVE = 512
    WM_LBUTTONDOWN = 513
    WM_LBUTTONUP = 514
    MK_LBUTTON = 1
    WM_ACTIVATE = 6
    WM_SETFOCUS = 7
    WM_SETCURSOR = 32
    WM_MOUSEACTIVATE = 33
    WA_ACTIVE = 1
    HTCLIENT = 1
    MA_ACTIVATE = 1
    MOUSEEVENTF_LEFTDOWN = 2
    MOUSEEVENTF_LEFTUP = 4


class RaisingPostMessageWin32Gui(FakeWin32Gui):
    def PostMessage(self, hwnd, message, wparam, lparam):
        self.calls.append(("win32gui.PostMessage", hwnd, message, wparam, lparam))
        raise RuntimeError("gui blocked")


class ChildWindowWin32Gui(FakeWin32Gui):
    def ChildWindowFromPointEx(self, hwnd, point, flags):
        self.calls.append(("ChildWindowFromPointEx", hwnd, point, flags))
        if hwnd == 1001:
            return 2002
        return hwnd

    def WindowFromPoint(self, point):
        self.calls.append(("WindowFromPoint", point))
        return 9999

    def GetAncestor(self, hwnd, flag):
        self.calls.append(("GetAncestor", hwnd, flag))
        return 1001

    def IsWindow(self, hwnd):
        return hwnd in {1001, 2002, 9999}

    def ScreenToClient(self, hwnd, point):
        self.calls.append(("ScreenToClient", hwnd, point))
        if hwnd == 2002:
            return point[0] - 130, point[1] - 240
        return super().ScreenToClient(hwnd, point)

    def PostMessage(self, hwnd, message, wparam, lparam):
        self.calls.append(("win32gui.PostMessage", hwnd, message, wparam, lparam))


class RecordingWin32Api:
    def __init__(self):
        self.calls = []

    def MAKELONG(self, x, y):
        return (y << 16) | x

    def PostMessage(self, hwnd, message, wparam, lparam):
        self.calls.append(("win32api.PostMessage", hwnd, message, wparam, lparam))


class RecordingWin32Gui(FakeWin32Gui):
    def PostMessage(self, hwnd, message, wparam, lparam):
        self.calls.append(("win32gui.PostMessage", hwnd, message, wparam, lparam))


class FakeImage:
    def __init__(self, width=20, height=20):
        self.shape = (height, width, 3)

    def __getitem__(self, _item):
        return self


class CountingCv2:
    IMREAD_COLOR = 1
    TM_CCOEFF_NORMED = 5

    def __init__(self):
        self.imread_calls = 0

    def imread(self, _path, _flags):
        self.imread_calls += 1
        return FakeImage(4, 4)

    def matchTemplate(self, _image, _template, _method):
        return "result"

    def minMaxLoc(self, _result):
        return 0.0, 0.99, (0, 0), (3, 5)


class FakeEncodedImage:
    def __init__(self):
        self.saved_path = ""

    def tofile(self, path):
        self.saved_path = path
        Path(path).write_bytes(b"encoded")


class EncodingCv2:
    def __init__(self):
        self.encoded = FakeEncodedImage()
        self.extension = ""

    def imencode(self, extension, _crop):
        self.extension = extension
        return True, self.encoded


class FakeDmClicker:
    def available(self):
        return True

    def find_template(self, _hwnd, _template_path, threshold, _roi=None):
        return DmFindResult(True, 10, 20, threshold, "DM_FIND_OK 10 20", "windows3")


class FakeGroupDmClicker(FakeDmClicker):
    def __init__(self):
        self.calls = []

    def find_templates(self, _hwnd, template_paths, threshold, _roi=None):
        self.calls.append([Path(path).name for path in template_paths])
        return DmFindResult(True, 30, 40, threshold, "DM_FIND_OK 1 30 40", "windows3", 1)


class AutomationWindowPickerTests(unittest.TestCase):
    def test_window_from_point_returns_top_level_window(self):
        automation = Win32Automation.__new__(Win32Automation)
        automation.win32gui = FakeWin32Gui()
        automation.win32con = FakeWin32Con()

        window = automation.window_from_point(100, 200)

        self.assertEqual(window, GameWindow(hwnd=10, title="斗罗大陆H5"))
        self.assertEqual(
            automation.win32gui.calls,
            [("WindowFromPoint", (100, 200)), ("GetAncestor", 20, 2)],
        )

    def test_bitblt_none_return_is_treated_as_success(self):
        self.assertFalse(_bitblt_failed(None))

    def test_bitblt_zero_or_false_return_is_treated_as_failure(self):
        self.assertTrue(_bitblt_failed(0))
        self.assertTrue(_bitblt_failed(False))

    def test_background_click_falls_back_to_win32api_post_message(self):
        automation = Win32Automation.__new__(Win32Automation)
        automation.win32gui = RaisingPostMessageWin32Gui()
        automation.win32api = RecordingWin32Api()
        automation.win32con = FakeWin32Con()

        clicked = automation.background_click(1001, 10, 20)

        self.assertTrue(clicked)
        self.assertEqual(len(automation.win32api.calls), 7)
        self.assertEqual(getattr(automation, "last_click_error", ""), "")

    def test_background_click_reports_access_denied_without_foreground_fallback(self):
        automation = Win32Automation.__new__(Win32Automation)
        automation.win32gui = RaisingPostMessageWin32Gui()
        automation.win32api = RecordingWin32Api()
        automation.win32con = FakeWin32Con()

        def blocked_post_message(hwnd, message, wparam, lparam):
            raise RuntimeError("(5, 'PostMessage', '拒绝访问。')")

        automation.win32api.PostMessage = blocked_post_message

        clicked = automation.background_click(1001, 10, 20)

        self.assertFalse(clicked)
        self.assertEqual(getattr(automation, "last_click_method", ""), "")
        self.assertIn("拒绝访问", getattr(automation, "last_click_error", ""))

    def test_background_click_targets_child_window_even_when_screen_point_is_obscured(self):
        automation = Win32Automation.__new__(Win32Automation)
        automation.win32gui = ChildWindowWin32Gui()
        automation.win32api = RecordingWin32Api()
        automation.win32con = FakeWin32Con()
        expected_lparam = automation.win32api.MAKELONG( -20, -20)

        clicked = automation.background_click(1001, 10, 20)

        self.assertTrue(clicked)
        self.assertEqual(getattr(automation, "last_click_target", None), 2002)
        self.assertIn(("ChildWindowFromPointEx", 1001, (10, 20), 0), automation.win32gui.calls)
        self.assertNotIn(("WindowFromPoint", (110, 220)), automation.win32gui.calls)
        post_calls = [call for call in automation.win32gui.calls if call[0] == "win32gui.PostMessage"]
        self.assertEqual(len(post_calls), 14)
        self.assertEqual([call[1] for call in post_calls[:7]], [2002] * 7)
        self.assertEqual([call[1] for call in post_calls[7:]], [1001] * 7)
        self.assertTrue(all(call[4] == expected_lparam for call in post_calls[:7]))

    def test_background_click_sends_background_focus_messages_before_mouse_click(self):
        automation = Win32Automation.__new__(Win32Automation)
        automation.win32gui = RecordingWin32Gui()
        automation.win32api = RecordingWin32Api()
        automation.win32con = FakeWin32Con()

        clicked = automation.background_click(1001, 10, 20)

        self.assertTrue(clicked)
        post_messages = [call[2] for call in automation.win32gui.calls if call[0] == "win32gui.PostMessage"]
        self.assertEqual(
            post_messages[:4],
            [
                FakeWin32Con.WM_MOUSEACTIVATE,
                FakeWin32Con.WM_ACTIVATE,
                FakeWin32Con.WM_SETFOCUS,
                FakeWin32Con.WM_SETCURSOR,
            ],
        )
        self.assertEqual(
            post_messages[-3:],
            [FakeWin32Con.WM_MOUSEMOVE, FakeWin32Con.WM_LBUTTONDOWN, FakeWin32Con.WM_LBUTTONUP],
        )

    def test_runtime_capture_uses_background_capture_without_foreground(self):
        automation = Win32Automation.__new__(Win32Automation)
        calls = []

        def background(hwnd):
            calls.append(("background", hwnd))
            return "image"

        def foreground(hwnd):
            calls.append(("foreground", hwnd))
            return "image"

        automation.capture_window_background = background
        automation.capture_window_foreground = foreground

        image = automation.capture_window(1001)

        self.assertEqual(image, "image")
        self.assertEqual(calls, [("background", 1001)])

    def test_find_template_reuses_cached_template_image(self):
        automation = Win32Automation.__new__(Win32Automation)
        automation.cv2 = CountingCv2()
        automation._template_cache = {}

        with TemporaryDirectory() as directory:
            template_path = Path(directory) / "button.bmp"
            template_path.write_bytes(b"fake")

            first = automation.find_template(FakeImage(), template_path, 0.5)
            second = automation.find_template(FakeImage(), template_path, 0.5)

        self.assertEqual(first, (5, 7, 0.99))
        self.assertEqual(second, (5, 7, 0.99))
        self.assertEqual(automation.cv2.imread_calls, 1)

    def test_find_template_in_window_converts_dm_top_left_to_center_point(self):
        automation = Win32Automation.__new__(Win32Automation)
        automation.cv2 = CountingCv2()
        automation._template_cache = {}
        automation.dm_clicker = FakeDmClicker()

        with TemporaryDirectory() as directory:
            template_path = Path(directory) / "button.bmp"
            template_path.write_bytes(b"fake")

            match = automation.find_template_in_window(1001, template_path, 0.86)

        self.assertEqual(match, (12, 22, 0.86))

    def test_find_any_template_in_window_uses_dm_group_matching(self):
        automation = Win32Automation.__new__(Win32Automation)
        automation.cv2 = CountingCv2()
        automation._template_cache = {}
        automation.dm_clicker = FakeGroupDmClicker()

        with TemporaryDirectory() as directory:
            first = Path(directory) / "a.bmp"
            second = Path(directory) / "b.bmp"
            first.write_bytes(b"fake")
            second.write_bytes(b"fake")

            result = automation.find_any_template_in_window(1001, [first, second], 0.86)

        self.assertEqual(result, (1, (32, 42, 0.86)))
        self.assertEqual(automation.dm_clicker.calls, [["a.bmp", "b.bmp"]])

    def test_save_crop_uses_encoded_write_for_unicode_paths(self):
        automation = Win32Automation.__new__(Win32Automation)
        automation.cv2 = EncodingCv2()

        with TemporaryDirectory() as directory:
            output = Path(directory) / "全自动辅助助手" / "模板.png"
            automation.save_crop(FakeImage(20, 20), (1, 2, 6, 8), output)

            self.assertTrue(output.exists())
            self.assertEqual(output.read_bytes(), b"encoded")
            self.assertEqual(automation.cv2.extension, ".png")


if __name__ == "__main__":
    unittest.main()
