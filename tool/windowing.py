from __future__ import annotations

import ctypes
import ctypes.util
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


def get_system_idle_seconds() -> float:
    if os.name == "nt":
        return _windows_idle_seconds()
    if sys_platform_is_macos():
        return _macos_idle_seconds()
    return 0.0


def sys_platform_is_macos() -> bool:
    return os.uname().sysname == "Darwin" if hasattr(os, "uname") else False


def _windows_idle_seconds() -> float:
    class LastInputInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("dwTime", wintypes.DWORD),
        ]

    info = LastInputInfo()
    info.cbSize = ctypes.sizeof(LastInputInfo)
    user32 = _windows_user32()
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    milliseconds = (
        ctypes.windll.kernel32.GetTickCount() - info.dwTime
    ) & 0xFFFFFFFF
    return milliseconds / 1000.0


@lru_cache(maxsize=1)
def _macos_application_services():
    path = ctypes.util.find_library("ApplicationServices")
    if not path:
        return None
    library = ctypes.CDLL(path)
    function = library.CGEventSourceSecondsSinceLastEventType
    function.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    function.restype = ctypes.c_double
    return function


def _macos_idle_seconds() -> float:
    function = _macos_application_services()
    if function is None:
        return 0.0
    return max(0.0, float(function(0, 0xFFFFFFFF)))


@lru_cache(maxsize=1)
def _windows_user32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetLastInputInfo.argtypes = [ctypes.c_void_p]
    user32.GetLastInputInfo.restype = wintypes.BOOL
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
