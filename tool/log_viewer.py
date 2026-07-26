from __future__ import annotations

import ctypes
import os
import sys
import time
from datetime import date
from pathlib import Path


def _parent_is_running(process_id: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(process_id, 0)
        except OSError:
            return False
        return True

    process = ctypes.windll.kernel32.OpenProcess(
        0x1000,
        False,
        process_id,
    )
    if not process:
        return False
    ctypes.windll.kernel32.CloseHandle(process)
    return True


def _configure_console() -> None:
    if os.name == "nt":
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleTitleW("AIpet 实时日志")
        # A GUI parent (pythonw.exe) has no usable standard output handles.
        # Bind directly to this process' newly-created console.
        sys.stdout = open(
            "CONOUT$",
            "w",
            encoding="utf-8",
            errors="replace",
            buffering=1,
        )
        sys.stderr = open(
            "CONOUT$",
            "w",
            encoding="utf-8",
            errors="replace",
            buffering=1,
        )
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _daily_log_path(log_directory: Path) -> Path:
    return log_directory / f"{date.today().isoformat()}.log"


def _print_recent(path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    with path.open("rb") as source:
        source.seek(0, os.SEEK_END)
        size = source.tell()
        source.seek(max(0, size - 256 * 1024))
        data = source.read()
        position = source.tell()
    lines = data.splitlines(keepends=True)[-200:]
    if lines:
        print(
            b"".join(lines).decode("utf-8", errors="replace"),
            end="",
            flush=True,
        )
    return position


def _print_appended(path: Path, position: int) -> int:
    try:
        size = path.stat().st_size
    except OSError:
        return position
    if size < position:
        position = 0
    if size == position:
        return position
    try:
        with path.open("rb") as source:
            source.seek(position)
            data = source.read()
            position = source.tell()
    except OSError:
        return position
    if data:
        print(
            data.decode("utf-8", errors="replace"),
            end="",
            flush=True,
        )
    return position


def follow(log_directory: Path, parent_process_id: int) -> None:
    _configure_console()
    print(f"AIpet 实时日志目录：{log_directory}")
    print("关闭此窗口不会退出 AIpet。\n")

    current_path = _daily_log_path(log_directory)
    position = _print_recent(current_path)
    while _parent_is_running(parent_process_id):
        next_path = _daily_log_path(log_directory)
        if next_path != current_path:
            current_path = next_path
            print(f"\n--- {current_path.name} ---", flush=True)
            position = _print_recent(current_path)
        else:
            position = _print_appended(current_path, position)
        time.sleep(0.15)


def main() -> int:
    if len(sys.argv) != 3:
        return 2
    follow(Path(sys.argv[1]), int(sys.argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
