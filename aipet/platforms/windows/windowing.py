"""Windows-native window integration."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from functools import lru_cache


HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200
TOPMOST_FLAGS = (
    SWP_NOSIZE
    | SWP_NOMOVE
    | SWP_NOACTIVATE
    | SWP_NOOWNERZORDER
)


def native_topmost_available() -> bool:
    return os.name == "nt"


def ensure_window_topmost(window_id: int) -> bool:
    """Reassert Windows TOPMOST state without moving or activating a window."""

    if not native_topmost_available() or not window_id:
        return False
    _set_windows_topmost(window_id, _windows_user32())
    return True


@lru_cache(maxsize=1)
def _windows_user32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    return user32


def _set_windows_topmost(window_id: int, user32) -> None:
    succeeded = user32.SetWindowPos(
        wintypes.HWND(window_id),
        wintypes.HWND(HWND_TOPMOST),
        0,
        0,
        0,
        0,
        TOPMOST_FLAGS,
    )
    if not succeeded:
        raise ctypes.WinError(ctypes.get_last_error())
