from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
APP_NAME = "全自动辅助助手"


def run(command: list[str]) -> None:
    print(" ".join(command))
    subprocess.run(command, cwd=PROJECT_DIR, check=True)


def stop_running_app() -> None:
    subprocess.run(["taskkill", "/F", "/IM", f"{APP_NAME}.exe"], cwd=PROJECT_DIR, check=False)


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    shutil.copytree(source, target, dirs_exist_ok=True)


def main() -> int:
    print("[1/5] Checking Python...")
    run([sys.executable, "--version"])

    print("[2/5] Installing PyInstaller if needed...")
    run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    print("[3/5] Running tests...")
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])

    print("[4/5] Running compile check...")
    run([sys.executable, "-m", "compileall", "h5bot", "main.py", "tests"])

    print("[5/5] Building onedir exe...")
    stop_running_app()
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--windowed",
            "--name",
            APP_NAME,
            "--distpath",
            str(PROJECT_DIR / "dist"),
            "--workpath",
            str(PROJECT_DIR / "build" / "pyinstaller"),
            "--specpath",
            str(PROJECT_DIR / "build"),
            "--hidden-import",
            "win32timezone",
            "--add-data",
            f"{PROJECT_DIR / 'assets'};assets",
            "--add-data",
            f"{PROJECT_DIR / 'config'};config",
            "--add-data",
            f"{PROJECT_DIR / 'docs'};docs",
            "main.py",
        ]
    )

    output_dir = PROJECT_DIR / "dist" / APP_NAME
    copy_tree(PROJECT_DIR / "assets", output_dir / "assets")
    copy_tree(PROJECT_DIR / "config", output_dir / "config")
    copy_tree(PROJECT_DIR / "docs", output_dir / "docs")

    print()
    print("Build complete:")
    print(output_dir / f"{APP_NAME}.exe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
