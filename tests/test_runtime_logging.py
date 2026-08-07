from __future__ import annotations

import io
import logging
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, call, patch

from main import run_special_mode
from aipet.core import runtime_logging
from aipet.platforms.windows import log_viewer
from aipet.platforms.windows.log_viewer import _print_appended, _print_recent
from aipet.core.runtime_logging import (
    DailyFileHandler,
    _console_python_executable,
    _viewer_command,
    configure_console_logging,
    format_json_for_log,
    get_logger,
    shutdown_console_logging,
)


class RuntimeLoggingTests(unittest.TestCase):
    def test_file_logging_stays_enabled_without_console_viewer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_directory = Path(directory)
            with (
                patch.object(runtime_logging, "LOG_DIRECTORY", log_directory),
                patch.object(
                    runtime_logging,
                    "LEGACY_LOG_PATH",
                    log_directory / "missing-legacy.log",
                ),
            ):
                try:
                    viewer_started = configure_console_logging(False)
                    get_logger("test").info("persistent log entry")
                finally:
                    shutdown_console_logging()

            path = log_directory / f"{date.today().isoformat()}.log"
            self.assertFalse(viewer_started)
            self.assertIn(
                "persistent log entry",
                path.read_text(encoding="utf-8"),
            )

    def test_daily_handler_writes_to_current_date_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            handler = DailyFileHandler(Path(directory))
            handler.setFormatter(logging.Formatter("%(message)s"))
            record = logging.LogRecord(
                "aipet.test",
                logging.INFO,
                __file__,
                1,
                "daily log entry",
                (),
                None,
            )
            handler.emit(record)
            handler.close()

            path = Path(directory) / f"{date.today().isoformat()}.log"
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "daily log entry\n",
            )

    def test_viewer_reads_content_appended_after_eof(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "daily.log"
            path.write_text("existing\n", encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                position = _print_recent(path)
                with path.open("a", encoding="utf-8") as log:
                    log.write("live update\n")
                    log.flush()
                position = _print_appended(path, position)

            self.assertEqual(position, path.stat().st_size)
            self.assertIn("existing", output.getvalue())
            self.assertIn("live update", output.getvalue())

    @unittest.skipUnless(
        sys.platform == "win32",
        "Windows console allocation is not part of the macOS adapter",
    )
    def test_viewer_allocates_console_before_opening_output(self) -> None:
        kernel32 = MagicMock()
        kernel32.GetConsoleWindow.return_value = 0
        kernel32.AllocConsole.return_value = 1
        stdout = MagicMock()
        stderr = MagicMock()

        with (
            patch.object(log_viewer.os, "name", "nt"),
            patch.object(
                log_viewer.ctypes,
                "WinDLL",
                return_value=kernel32,
            ) as win_dll,
            patch.object(
                log_viewer,
                "open",
                side_effect=[stdout, stderr],
                create=True,
            ) as open_console,
            patch.object(log_viewer.sys, "stdout", None),
            patch.object(log_viewer.sys, "stderr", None),
        ):
            log_viewer._configure_console()

        win_dll.assert_called_once_with("kernel32", use_last_error=True)
        kernel32.GetConsoleWindow.assert_called_once_with()
        kernel32.AllocConsole.assert_called_once_with()
        self.assertEqual(
            open_console.call_args_list,
            [
                call(
                    "CONOUT$",
                    "w",
                    encoding="utf-8",
                    errors="replace",
                    buffering=1,
                ),
                call(
                    "CONOUT$",
                    "w",
                    encoding="utf-8",
                    errors="replace",
                    buffering=1,
                ),
            ],
        )

    def test_json_log_keeps_payload_and_compacts_base64_images(self) -> None:
        image = "a" * 2_048
        output = format_json_for_log(
            {
                "model": "vision-model",
                "messages": [{"images": [image]}],
                "api_key": "do-not-log-this",
                "autodl_password_encrypted": "encrypted-password-token",
            }
        )

        self.assertIn('"model": "vision-model"', output)
        self.assertIn("数据已省略", output)
        self.assertIn("字符数=2048", output)
        self.assertNotIn(image, output)
        self.assertNotIn("do-not-log-this", output)
        self.assertNotIn("encrypted-password-token", output)

    @unittest.skipUnless(
        sys.platform == "win32",
        "pythonw.exe resolution is a Windows-only log-viewer concern",
    )
    def test_console_viewer_uses_python_instead_of_pythonw(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / "python.exe"
            pythonw = root / "pythonw.exe"
            python.touch()
            pythonw.touch()

            self.assertEqual(
                _console_python_executable(str(pythonw)),
                str(python),
            )
            self.assertEqual(
                _console_python_executable(str(python)),
                str(python),
            )

    @unittest.skipUnless(
        sys.platform == "win32",
        "The console log viewer is a Windows-only feature",
    )
    def test_source_viewer_command_runs_log_viewer_script(self) -> None:
        with (
            patch.object(runtime_logging.sys, "executable", "python.exe"),
            patch.object(
                runtime_logging.sys,
                "frozen",
                False,
                create=True,
            ),
        ):
            command = _viewer_command(Path("C:/logs"), 123)

        self.assertEqual(
            command,
            [
                "python.exe",
                str(runtime_logging.LOG_VIEWER),
                "C:\\logs",
                "123",
            ],
        )

    @unittest.skipUnless(
        sys.platform == "win32",
        "The console log viewer is a Windows-only feature",
    )
    def test_frozen_viewer_command_reuses_exe_special_mode(self) -> None:
        with (
            patch.object(runtime_logging.sys, "executable", "AIpet.exe"),
            patch.object(
                runtime_logging.sys,
                "frozen",
                True,
                create=True,
            ),
        ):
            command = _viewer_command(Path("C:/logs"), 123)

        self.assertEqual(
            command,
            ["AIpet.exe", "--log-viewer", "C:\\logs", "123"],
        )

    @unittest.skipUnless(
        sys.platform == "win32",
        "The console log viewer is a Windows-only feature",
    )
    def test_main_dispatches_log_viewer_special_mode(self) -> None:
        with patch("aipet.platforms.windows.log_viewer.follow") as follow:
            result = run_special_mode(
                ["AIpet.exe", "--log-viewer", "C:/logs", "123"]
            )

        self.assertEqual(result, 0)
        follow.assert_called_once_with(Path("C:/logs"), 123)
        self.assertIsNone(run_special_mode(["AIpet.exe"]))


if __name__ == "__main__":
    unittest.main()
