from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from h5bot.dm_clicker import DmSoftClicker


@dataclass(slots=True)
class GameWindow:
    hwnd: int
    title: str


class DependencyError(RuntimeError):
    pass


class Win32Automation:
    def __init__(self) -> None:
        self.win32gui, self.win32ui, self.win32con, self.win32api = _load_win32()
        self.cv2 = _load_cv2()
        self.np = _load_numpy()
        self.last_click_error = ""
        self.last_click_method = ""
        self.last_click_target = 0
        self.dm_clicker = DmSoftClicker()
        self._template_cache = {}

    def find_windows(self, keyword: str) -> list[GameWindow]:
        windows: list[GameWindow] = []

        def callback(hwnd, _extra):
            if not self.win32gui.IsWindowVisible(hwnd):
                return
            title = self.win32gui.GetWindowText(hwnd)
            if keyword and keyword in title:
                windows.append(GameWindow(hwnd=hwnd, title=title))

        self.win32gui.EnumWindows(callback, None)
        return windows

    def window_from_point(self, x: int, y: int) -> GameWindow | None:
        hwnd = self.win32gui.WindowFromPoint((int(x), int(y)))
        if not hwnd:
            return None
        root_hwnd = self.win32gui.GetAncestor(hwnd, getattr(self.win32con, "GA_ROOT", 2))
        hwnd = root_hwnd or hwnd
        if not self.win32gui.IsWindow(hwnd):
            return None
        title = self.win32gui.GetWindowText(hwnd) or f"窗口 {hwnd}"
        return GameWindow(hwnd=hwnd, title=title)

    def capture_window(self, hwnd: int):
        return self.capture_window_background(hwnd)

    def capture_window_background(self, hwnd: int):
        left, top, right, bottom = self.win32gui.GetClientRect(hwnd)
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            raise RuntimeError("窗口客户区尺寸无效，可能被最小化或不可见")

        hwnd_dc = self.win32gui.GetDC(hwnd)
        source_dc = self.win32ui.CreateDCFromHandle(hwnd_dc)
        memory_dc = source_dc.CreateCompatibleDC()
        bitmap = self.win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        memory_dc.SelectObject(bitmap)

        try:
            ok = memory_dc.BitBlt((0, 0), (width, height), source_dc, (0, 0), self.win32con.SRCCOPY)
            if _bitblt_failed(ok):
                raise RuntimeError("后台截图失败，目标窗口可能不支持窗口 DC 截图")
            info = bitmap.GetInfo()
            bits = bitmap.GetBitmapBits(True)
            image = self.np.frombuffer(bits, dtype=self.np.uint8)
            image.shape = (info["bmHeight"], info["bmWidth"], 4)
            return self.cv2.cvtColor(image, self.cv2.COLOR_BGRA2BGR)
        finally:
            self.win32gui.DeleteObject(bitmap.GetHandle())
            memory_dc.DeleteDC()
            source_dc.DeleteDC()
            self.win32gui.ReleaseDC(hwnd, hwnd_dc)

    def capture_window_foreground(self, hwnd: int):
        left, top, right, bottom = self.win32gui.GetClientRect(hwnd)
        width = right - left
        height = bottom - top
        if width <= 0 or height <= 0:
            raise RuntimeError("窗口客户区尺寸无效，可能被最小化或不可见")

        self._bring_to_foreground(hwnd)
        screen_left, screen_top = self.win32gui.ClientToScreen(hwnd, (0, 0))
        screen_dc = self.win32gui.GetDC(0)
        source_dc = self.win32ui.CreateDCFromHandle(screen_dc)
        memory_dc = source_dc.CreateCompatibleDC()
        bitmap = self.win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        memory_dc.SelectObject(bitmap)

        try:
            ok = memory_dc.BitBlt((0, 0), (width, height), source_dc, (screen_left, screen_top), self.win32con.SRCCOPY)
            if _bitblt_failed(ok):
                raise RuntimeError("前台截图失败，请确认窗口未被遮挡且客户区可见")
            info = bitmap.GetInfo()
            bits = bitmap.GetBitmapBits(True)
            image = self.np.frombuffer(bits, dtype=self.np.uint8)
            image.shape = (info["bmHeight"], info["bmWidth"], 4)
            return self.cv2.cvtColor(image, self.cv2.COLOR_BGRA2BGR)
        finally:
            self.win32gui.DeleteObject(bitmap.GetHandle())
            memory_dc.DeleteDC()
            source_dc.DeleteDC()
            self.win32gui.ReleaseDC(0, screen_dc)

    def _bring_to_foreground(self, hwnd: int) -> None:
        try:
            self.win32gui.ShowWindow(hwnd, getattr(self.win32con, "SW_RESTORE", 9))
            self.win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.12)
        except Exception:
            time.sleep(0.12)

    def find_template(self, image, template_path: Path | str, threshold: float, roi: list[int] | None = None):
        path = Path(template_path)
        if not path.exists():
            return None
        template = self._read_template(path)
        if template is None:
            return None
        search_image = image
        offset_x = 0
        offset_y = 0
        if roi:
            x1, y1, x2, y2 = [int(part) for part in roi]
            left, right = sorted((max(0, x1), max(0, x2)))
            top, bottom = sorted((max(0, y1), max(0, y2)))
            right = min(right, image.shape[1])
            bottom = min(bottom, image.shape[0])
            if right <= left or bottom <= top:
                return None
            search_image = image[top:bottom, left:right]
            offset_x = left
            offset_y = top
        if search_image.shape[0] < template.shape[0] or search_image.shape[1] < template.shape[1]:
            return None

        result = self.cv2.matchTemplate(search_image, template, self.cv2.TM_CCOEFF_NORMED)
        _min_val, max_val, _min_loc, max_loc = self.cv2.minMaxLoc(result)
        if max_val < threshold:
            return None
        center_x = offset_x + max_loc[0] + template.shape[1] // 2
        center_y = offset_y + max_loc[1] + template.shape[0] // 2
        return center_x, center_y, float(max_val)

    def find_template_in_window(self, hwnd: int, template_path: Path | str, threshold: float, roi: list[int] | None = None):
        self.last_recognition_backend = ""
        dm_clicker = getattr(self, "dm_clicker", None)
        if dm_clicker and dm_clicker.available():
            dm_result = dm_clicker.find_template(hwnd, template_path, threshold, roi)
            if dm_result.ok:
                self.last_recognition_backend = "大漠"
                template = self._read_template(Path(template_path))
                if template is not None:
                    return dm_result.x + template.shape[1] // 2, dm_result.y + template.shape[0] // 2, dm_result.score
                return dm_result.x, dm_result.y, dm_result.score
            if dm_result.message == "not_found":
                return None
        image = self.capture_window(hwnd)
        self.last_recognition_backend = "OpenCV"
        return self.find_template(image, template_path, threshold, roi)

    def find_any_template_in_window(self, hwnd: int, template_paths: list[Path | str], threshold: float, roi: list[int] | None = None):
        self.last_recognition_backend = ""
        paths = [Path(path) for path in template_paths]
        dm_clicker = getattr(self, "dm_clicker", None)
        if dm_clicker and dm_clicker.available():
            for group_start, group in _group_paths_by_parent(paths):
                dm_result = dm_clicker.find_templates(hwnd, group, threshold, roi)
                if dm_result.ok:
                    self.last_recognition_backend = "大漠"
                    matched_index = group_start + dm_result.index
                    if 0 <= matched_index < len(paths):
                        matched_path = paths[matched_index]
                        template = self._read_template(matched_path)
                        if template is not None:
                            match = dm_result.x + template.shape[1] // 2, dm_result.y + template.shape[0] // 2, dm_result.score
                        else:
                            match = dm_result.x, dm_result.y, dm_result.score
                        return matched_index, match
                if dm_result.message != "not_found":
                    break
        image = self.capture_window(hwnd)
        self.last_recognition_backend = "OpenCV"
        for index, path in enumerate(paths):
            match = self.find_template(image, path, threshold, roi)
            if match:
                return index, match
        return None

    def _read_template(self, path: Path):
        cache = getattr(self, "_template_cache", None)
        if cache is None:
            cache = {}
            self._template_cache = cache
        key = str(path.resolve())
        if key not in cache:
            cache[key] = self.cv2.imread(str(path), self.cv2.IMREAD_COLOR)
        return cache[key]

    def background_click(self, hwnd: int, x: int, y: int) -> bool:
        self.last_click_error = ""
        self.last_click_method = ""
        self.last_click_target = 0
        dm_clicker = getattr(self, "dm_clicker", None)
        dm_error = ""
        if dm_clicker:
            dm_result = dm_clicker.click(hwnd, int(x), int(y))
            if dm_result.ok:
                self.last_click_method = f"dmsoft:{dm_result.mode}" if dm_result.mode else "dmsoft"
                self.last_click_target = hwnd
                return True
            dm_error = dm_clicker.last_error
            if dm_clicker.available():
                self.last_click_error = f"dmsoft: {dm_error or dm_result.message}"
                return False
        target_hwnd, target_x, target_y = self._click_target(hwnd, int(x), int(y))
        messages = [
            (self.win32con.WM_MOUSEMOVE, 0),
            (self.win32con.WM_LBUTTONDOWN, self.win32con.MK_LBUTTON),
            (self.win32con.WM_LBUTTONUP, 0),
        ]
        targets = [(target_hwnd, target_x, target_y)]
        if target_hwnd != hwnd:
            targets.append((hwnd, int(x), int(y)))
        try:
            self._post_click_to_targets(self.win32gui.PostMessage, targets, messages)
            self.last_click_method = "background"
            self.last_click_target = target_hwnd
            return True
        except Exception as gui_exc:
            try:
                self._post_click_to_targets(self.win32api.PostMessage, targets, messages)
                self.last_click_method = "background"
                self.last_click_target = target_hwnd
                return True
            except Exception as api_exc:
                dm_suffix = f"dmsoft: {dm_error}; " if dm_error else ""
                self.last_click_error = f"{dm_suffix}win32gui.PostMessage: {gui_exc}; win32api.PostMessage: {api_exc}"
                return False

    def shutdown(self) -> None:
        dm_clicker = getattr(self, "dm_clicker", None)
        if dm_clicker:
            dm_clicker.shutdown()

    def _click_target(self, hwnd: int, x: int, y: int) -> tuple[int, int, int]:
        target_hwnd = self._child_window_from_client_point(hwnd, int(x), int(y))
        if not target_hwnd or target_hwnd == hwnd:
            return hwnd, x, y
        screen_point = self.win32gui.ClientToScreen(hwnd, (int(x), int(y)))
        target_x, target_y = self.win32gui.ScreenToClient(target_hwnd, screen_point)
        return target_hwnd, int(target_x), int(target_y)

    def _child_window_from_client_point(self, hwnd: int, x: int, y: int) -> int:
        child_from_point = getattr(self.win32gui, "ChildWindowFromPointEx", None)
        if not child_from_point:
            return hwnd
        try:
            child = child_from_point(hwnd, (int(x), int(y)), 0)
        except Exception:
            return hwnd
        if not child or not self._belongs_to_root(child, hwnd):
            return hwnd
        return child

    def _post_click_to_targets(self, post_message, targets: list[tuple[int, int, int]], messages: list[tuple[int, int]]) -> None:
        for target_hwnd, target_x, target_y in targets:
            lparam = self.win32api.MAKELONG(int(target_x), int(target_y))
            self._post_background_focus_messages(post_message, target_hwnd, lparam)
            self._post_click_messages(post_message, target_hwnd, messages, lparam)

    def _post_background_focus_messages(self, post_message, hwnd: int, lparam: int) -> None:
        focus_messages = [
            (getattr(self.win32con, "WM_MOUSEACTIVATE", 0x0021), getattr(self.win32con, "MA_ACTIVATE", 1)),
            (getattr(self.win32con, "WM_ACTIVATE", 0x0006), getattr(self.win32con, "WA_ACTIVE", 1)),
            (getattr(self.win32con, "WM_SETFOCUS", 0x0007), 0),
            (getattr(self.win32con, "WM_SETCURSOR", 0x0020), getattr(self.win32con, "HTCLIENT", 1)),
        ]
        for message, wparam in focus_messages:
            post_message(hwnd, message, wparam, lparam)

    def _belongs_to_root(self, child_hwnd: int, root_hwnd: int) -> bool:
        if child_hwnd == root_hwnd:
            return True
        try:
            return self.win32gui.GetAncestor(child_hwnd, getattr(self.win32con, "GA_ROOT", 2)) == root_hwnd
        except Exception:
            return False

    def _post_click_messages(self, post_message, hwnd: int, messages: list[tuple[int, int]], lparam: int) -> None:
        for index, (message, wparam) in enumerate(messages):
            post_message(hwnd, message, wparam, lparam)
            if index == 0:
                time.sleep(0.03)
            elif index == 1:
                time.sleep(0.05)

    def save_crop(self, image, rect: tuple[int, int, int, int], path: Path) -> None:
        x1, y1, x2, y2 = rect
        left, right = sorted((max(0, x1), max(0, x2)))
        top, bottom = sorted((max(0, y1), max(0, y2)))
        if right <= left or bottom <= top:
            raise ValueError("裁剪区域无效")
        crop = image[top:bottom, left:right]
        path.parent.mkdir(parents=True, exist_ok=True)
        ok, encoded = self.cv2.imencode(path.suffix or ".png", crop)
        if not ok:
            raise RuntimeError(f"保存模板失败: {path}")
        encoded.tofile(str(path))


def _load_win32():
    try:
        import win32api
        import win32con
        import win32gui
        import win32ui
    except ImportError as exc:
        raise DependencyError("缺少 pywin32，请先安装 requirements.txt 中的依赖") from exc
    return win32gui, win32ui, win32con, win32api


def _load_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise DependencyError("缺少 opencv-python，请先安装 requirements.txt 中的依赖") from exc
    return cv2


def _load_numpy():
    try:
        import numpy
    except ImportError as exc:
        raise DependencyError("缺少 numpy，请先安装 requirements.txt 中的依赖") from exc
    return numpy


def _bitblt_failed(result) -> bool:
    return result is False or result == 0


def _group_paths_by_parent(paths: list[Path]) -> list[tuple[int, list[Path]]]:
    groups: list[tuple[int, list[Path]]] = []
    current_parent = None
    current_start = 0
    current_group: list[Path] = []
    for index, path in enumerate(paths):
        parent = path.parent
        if current_group and parent != current_parent:
            groups.append((current_start, current_group))
            current_group = []
            current_start = index
        current_parent = parent
        current_group.append(path)
    if current_group:
        groups.append((current_start, current_group))
    return groups
