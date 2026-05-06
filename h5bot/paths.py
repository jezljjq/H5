from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundled_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", app_root())).resolve()


def resource_path(*parts: str | Path) -> Path:
    relative = Path(*parts)
    external = app_root() / relative
    if external.exists():
        return external
    return bundled_root() / relative


def writable_path(*parts: str | Path) -> Path:
    return app_root() / Path(*parts)
