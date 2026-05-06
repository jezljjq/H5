from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from h5bot.paths import app_root, writable_path


ROOT = app_root()
DEFAULT_DM_DLL = Path(r"E:\Program Files\大漠插件\dm密码是1234\7.2607\dm.dll")
DEFAULT_LICENSE_PATH = writable_path("config", "dm_license.json")
REGSVR32 = Path(r"C:\Windows\SysWOW64\regsvr32.exe")
MOUSE_MODES = ["windows3", "windows2", "windows"]
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


@dataclass(slots=True)
class DmClickResult:
    ok: bool
    message: str = ""
    mode: str = ""


@dataclass(slots=True)
class DmFindResult:
    ok: bool
    x: int = 0
    y: int = 0
    score: float = 0.0
    message: str = ""
    mode: str = ""
    index: int = -1


class DmSoftClicker:
    def __init__(
        self,
        dm_dll: Path = DEFAULT_DM_DLL,
        regsvr32: Path = REGSVR32,
        license_path: Path = DEFAULT_LICENSE_PATH,
    ) -> None:
        self.dm_dll = dm_dll
        self.regsvr32 = regsvr32
        self.license_path = license_path
        self.last_error = ""
        self._sessions: dict[int, DmWindowSession] = {}
        self._sessions_lock = threading.Lock()
        self._registered = False

    def available(self) -> bool:
        if not self.dm_dll.exists():
            return False
        try:
            import win32com.client  # noqa: F401
        except ImportError:
            return False
        return True

    def click(self, hwnd: int, x: int, y: int) -> DmClickResult:
        self.last_error = ""
        if not self.available():
            return DmClickResult(False, "大漠组件或 pywin32 不存在")
        try:
            result = self._session(int(hwnd)).click(int(x), int(y))
        except Exception as exc:
            self.last_error = str(exc)
            self._drop_session(int(hwnd))
            return DmClickResult(False, self.last_error)
        if not result.ok:
            self.last_error = result.message
            self._drop_session(int(hwnd))
        return result

    def find_template(self, hwnd: int, template_path: Path | str, threshold: float, roi: list[int] | None = None) -> DmFindResult:
        self.last_error = ""
        path = Path(template_path)
        if not self.available():
            return DmFindResult(False, message="大漠组件或 pywin32 不存在")
        if not path.exists():
            return DmFindResult(False, message="not_found")
        try:
            result = self._session(int(hwnd)).find_template(path, float(threshold), roi)
        except Exception as exc:
            self.last_error = str(exc)
            self._drop_session(int(hwnd))
            return DmFindResult(False, message=str(exc))
        if not result.ok and result.message != "not_found":
            self.last_error = result.message
            self._drop_session(int(hwnd))
        return result

    def find_templates(self, hwnd: int, template_paths: list[Path | str], threshold: float, roi: list[int] | None = None) -> DmFindResult:
        self.last_error = ""
        paths = [Path(path) for path in template_paths]
        if not self.available():
            return DmFindResult(False, message="大漠组件或 pywin32 不存在")
        if not paths or any(not path.exists() for path in paths):
            return DmFindResult(False, message="not_found")
        try:
            result = self._session(int(hwnd)).find_templates(paths, float(threshold), roi)
        except Exception as exc:
            self.last_error = str(exc)
            self._drop_session(int(hwnd))
            return DmFindResult(False, message=str(exc))
        if not result.ok and result.message != "not_found":
            self.last_error = result.message
            self._drop_session(int(hwnd))
        return result

    def shutdown(self) -> None:
        with self._sessions_lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close()

    def _session(self, hwnd: int) -> "DmWindowSession":
        with self._sessions_lock:
            session = self._sessions.get(hwnd)
            if session and session.alive:
                return session
            self._ensure_registered()
            license_data = self._load_license()
            session = DmWindowSession(
                hwnd=hwnd,
                modes=MOUSE_MODES,
                registration_code=license_data.get("registration_code", ""),
                extra_code=license_data.get("extra_code", ""),
            )
            session.start()
            self._sessions[hwnd] = session
            return session

    def _drop_session(self, hwnd: int) -> None:
        with self._sessions_lock:
            session = self._sessions.pop(hwnd, None)
        if session:
            session.close()

    def _load_license(self) -> dict[str, str]:
        if not self.license_path.exists():
            return {}
        try:
            data = json.loads(self.license_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return {
            "registration_code": str(data.get("registration_code", "")),
            "extra_code": str(data.get("extra_code", "")),
        }

    def _ensure_registered(self) -> None:
        if self._registered:
            return
        if self.regsvr32.exists() and self.dm_dll.exists():
            subprocess.run(
                [str(self.regsvr32), "/s", str(self.dm_dll)],
                capture_output=True,
                creationflags=CREATE_NO_WINDOW,
                timeout=8,
            )
        self._registered = True


class DmWindowSession:
    def __init__(
        self,
        hwnd: int,
        modes: list[str],
        registration_code: str = "",
        extra_code: str = "",
    ) -> None:
        self.hwnd = hwnd
        self.modes = modes
        self.registration_code = registration_code
        self.extra_code = extra_code
        self.mode = ""
        self.dm = None
        self.alive = False
        self._lock = threading.Lock()
        self._com_initialized = False
        self._current_path = ""

    def start(self) -> None:
        if self.alive:
            return
        pythoncom = _import_pythoncom()
        pythoncom.CoInitialize()
        self._com_initialized = True
        win32com_client = _import_win32com_client()
        try:
            self.dm = win32com_client.Dispatch("dm.dmsoft")
            if self.registration_code:
                reg_ret = self.dm.Reg(self.registration_code, self.extra_code)
                if reg_ret != 1:
                    raise RuntimeError(_explain_reg_return(f"DM_CLICK_FAIL RegRet {reg_ret}"))
            for mode in self.modes:
                try:
                    bind_ret = self.dm.BindWindow(int(self.hwnd), "normal", mode, "windows", 0)
                except Exception:
                    bind_ret = 0
                if bind_ret == 1:
                    self.mode = mode
                    self.alive = True
                    return
            raise RuntimeError(f"DM_WORKER_FAIL BindWindow modes={'|'.join(self.modes)}")
        except Exception:
            self.close()
            raise

    def click(self, x: int, y: int) -> DmClickResult:
        with self._lock:
            if not self.alive or self.dm is None:
                return DmClickResult(False, "大漠窗口未绑定", self.mode)
            self.dm.MoveTo(int(x), int(y))
            self.dm.LeftClick()
            return DmClickResult(True, f"DM_CLICK_OK {self.mode}", self.mode)

    def find_template(self, template_path: Path, threshold: float, roi: list[int] | None = None) -> DmFindResult:
        return self.find_templates([template_path], threshold, roi)

    def find_templates(self, template_paths: list[Path], threshold: float, roi: list[int] | None = None) -> DmFindResult:
        with self._lock:
            if not self.alive or self.dm is None:
                return DmFindResult(False, message="大漠窗口未绑定", mode=self.mode)
            if not template_paths:
                return DmFindResult(False, message="not_found", mode=self.mode)
            x1, y1, x2, y2 = _normalize_roi(roi)
            parent = template_paths[0].parent
            pic_name = "|".join(path.name for path in template_paths)
            parent_text = str(parent).replace("/", "\\")
            if parent_text != self._current_path:
                self.dm.SetPath(parent_text)
                self._current_path = parent_text
            result = self.dm.FindPic(
                int(x1),
                int(y1),
                int(x2),
                int(y2),
                pic_name,
                "000000",
                float(threshold),
                0,
                -1,
                -1,
            )
            index, x, y = _unpack_find_pic_result(result)
            if index >= 0:
                return DmFindResult(True, int(x), int(y), float(threshold), f"DM_FIND_OK {index} {x} {y}", self.mode, index)
            return DmFindResult(False, message="not_found", mode=self.mode)

    def close(self) -> None:
        try:
            if self.dm is not None:
                self.dm.UnBindWindow()
        except Exception:
            pass
        self.dm = None
        self.alive = False
        if self._com_initialized:
            try:
                _import_pythoncom().CoUninitialize()
            except Exception:
                pass
            self._com_initialized = False


def _unpack_find_pic_result(result) -> tuple[int, int, int]:
    if isinstance(result, tuple):
        index = int(result[0]) if len(result) > 0 else -1
        x = int(result[1]) if len(result) > 1 else -1
        y = int(result[2]) if len(result) > 2 else -1
        return index, x, y
    return int(result), -1, -1


def _normalize_roi(roi: list[int] | None) -> tuple[int, int, int, int]:
    if not roi:
        return 0, 0, 9999, 9999
    x1, y1, x2, y2 = [int(part) for part in roi]
    left, right = sorted((max(0, x1), max(0, x2)))
    top, bottom = sorted((max(0, y1), max(0, y2)))
    return left, top, right, bottom


def _reg_return_message(code: str) -> str:
    messages = {
        "-1": "无法连接大漠验证服务器，可能被防火墙拦截",
        "-2": "调用大漠注册的进程不是管理员权限",
        "0": "未知错误",
        "2": "余额不足",
        "3": "已绑定本机但账户余额不足",
        "4": "注册码错误",
        "5": "机器或 IP 在黑名单中，或不在白名单中",
        "8": "附加码不在白名单中",
    }
    return messages.get(str(code), "未识别的大漠注册返回码")


def _explain_reg_return(output: str) -> str:
    marker = "DM_CLICK_FAIL RegRet "
    if not output.startswith(marker):
        return output
    parts = output.split()
    if len(parts) < 3:
        return output
    return f"{output} {_reg_return_message(parts[2])}"


def _import_pythoncom():
    try:
        import pythoncom
    except ImportError as exc:
        raise RuntimeError("缺少 pywin32，请在 32 位 Python 中安装 pywin32") from exc
    return pythoncom


def _import_win32com_client():
    try:
        import win32com.client
    except ImportError as exc:
        raise RuntimeError("缺少 pywin32，请在 32 位 Python 中安装 pywin32") from exc
    retu