"""Windows subprocess policies and Job Object lifetime management."""

from __future__ import annotations

import ctypes
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


class WindowsKillOnCloseJob:
    """Keep managed child processes tied to the AIpet process lifetime."""

    _KILL_ON_JOB_CLOSE = 0x00002000
    _EXTENDED_LIMIT_INFORMATION = 9

    def __init__(self) -> None:
        self._handle: int | None = None

    def assign(self, process: Any) -> None:
        from ctypes import wintypes

        class BasicLimitInformation(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class ExtendedLimitInformation(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimitInformation),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [
            ctypes.c_void_p,
            wintypes.LPCWSTR,
        ]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
        ]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL

        if self._handle is None:
            handle = kernel32.CreateJobObjectW(None, None)
            if not handle:
                raise ctypes.WinError(ctypes.get_last_error())
            information = ExtendedLimitInformation()
            information.BasicLimitInformation.LimitFlags = (
                self._KILL_ON_JOB_CLOSE
            )
            if not kernel32.SetInformationJobObject(
                handle,
                self._EXTENDED_LIMIT_INFORMATION,
                ctypes.byref(information),
                ctypes.sizeof(information),
            ):
                error = ctypes.WinError(ctypes.get_last_error())
                self._close_handle(int(handle))
                raise error
            self._handle = int(handle)

        process_handle = getattr(process, "_handle", None)
        if process_handle is None:
            return
        if not kernel32.AssignProcessToJobObject(
            wintypes.HANDLE(self._handle),
            wintypes.HANDLE(int(process_handle)),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is not None:
            self._close_handle(handle)

    @staticmethod
    def _close_handle(handle: int) -> None:
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle(wintypes.HANDLE(handle))


class WindowsProcessPolicy:
    def hidden_subprocess_options(self) -> dict[str, Any]:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {
            "startupinfo": startupinfo,
            "creationflags": subprocess.CREATE_NO_WINDOW,
        }

    def new_console_subprocess_options(self) -> dict[str, Any]:
        return {"creationflags": subprocess.CREATE_NEW_CONSOLE}

    def console_python_executable(self, executable: str) -> str:
        path = Path(executable)
        if path.name.lower() != "pythonw.exe":
            return str(path)
        console_python = path.with_name("python.exe")
        return str(console_python) if console_python.is_file() else str(path)

    def create_child_process_guard(self) -> WindowsKillOnCloseJob:
        return WindowsKillOnCloseJob()

    def runtime_python_candidates(
        self,
        engine_root: Path,
    ) -> Sequence[Path]:
        return (
            engine_root / "runtime" / "python.exe",
            engine_root / "python.exe",
        )

    def log_viewer_command(
        self,
        executable: str,
        log_directory: Path,
        parent_process_id: int,
        *,
        frozen: bool,
        viewer_script: Path,
    ) -> list[str]:
        if frozen:
            return [
                executable,
                "--log-viewer",
                str(log_directory),
                str(parent_process_id),
            ]
        return [
            self.console_python_executable(executable),
            str(viewer_script),
            str(log_directory),
            str(parent_process_id),
        ]

    def follow_log_viewer(
        self,
        log_directory: Path,
        parent_process_id: int,
    ) -> None:
        from aipet.platforms.windows.log_viewer import follow

        follow(log_directory, parent_process_id)
