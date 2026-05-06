from __future__ import annotations

import ctypes
import os
import sys


def main() -> int:
    if os.name == "nt" and not _is_running_as_admin():
        return _relaunch_as_admin()
    try:
        from h5bot.automation import DependencyError
        from h5bot.ui import run_app

        return run_app()
    except Exception as exc:
        try:
            from h5bot.automation import DependencyError
        except Exception:
            DependencyError = RuntimeError
        if not isinstance(exc, DependencyError):
            raise
        print(exc)
        return 1


def _is_running_as_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _relaunch_as_admin() -> int:
    executable, params = _build_elevation_command(sys.executable, sys.argv)
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    if result <= 32:
        print("管理员权限启动失败或已取消")
        return 1
    return 0


def _build_elevation_command(executable: str, argv: list[str]) -> tuple[str, str]:
    params = " ".join(_quote_arg(arg) for arg in argv)
    return executable, params


def _quote_arg(value: str) -> str:
    escaped = value.replace('"', r'\"')
    return f'"{escaped}"'


if __name__ == "__main__":
    raise SystemExit(main())
