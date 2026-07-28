"""Native macOS window integration."""

from __future__ import annotations

import ctypes
import ctypes.util


_CAN_JOIN_ALL_SPACES = 1 << 0
_FULL_SCREEN_AUXILIARY = 1 << 8
_STATUS_WINDOW_LEVEL = 25


class _ObjectiveCRuntime:
    def __init__(self) -> None:
        library = ctypes.util.find_library("objc")
        if not library:
            raise OSError("Objective-C runtime is unavailable.")
        self._objc = ctypes.CDLL(library)
        self._objc.sel_registerName.argtypes = [ctypes.c_char_p]
        self._objc.sel_registerName.restype = ctypes.c_void_p

    def _selector(self, name: str) -> ctypes.c_void_p:
        return self._objc.sel_registerName(name.encode("ascii"))

    def object_result(self, receiver: int, selector: str) -> int:
        send = self._objc.objc_msgSend
        send.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        send.restype = ctypes.c_void_p
        return int(send(receiver, self._selector(selector)) or 0)

    def set_integer(self, receiver: int, selector: str, value: int) -> None:
        send = self._objc.objc_msgSend
        send.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_long,
        ]
        send.restype = None
        send(receiver, self._selector(selector), value)

    def set_bool(self, receiver: int, selector: str, value: bool) -> None:
        send = self._objc.objc_msgSend
        send.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_bool,
        ]
        send.restype = None
        send(receiver, self._selector(selector), value)


def configure_native_window(window_id: int) -> bool:
    if not window_id:
        return False
    runtime = _ObjectiveCRuntime()
    window = runtime.object_result(window_id, "window")
    if not window:
        return False
    runtime.set_integer(
        window,
        "setCollectionBehavior:",
        _CAN_JOIN_ALL_SPACES | _FULL_SCREEN_AUXILIARY,
    )
    runtime.set_integer(window, "setLevel:", _STATUS_WINDOW_LEVEL)
    runtime.set_bool(window, "setHidesOnDeactivate:", False)
    runtime.set_bool(window, "setCanHide:", False)
    return True


__all__ = ["configure_native_window"]
