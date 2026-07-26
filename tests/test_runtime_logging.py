from __future__ import annotations

import io
import logging
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from tool.log_viewer import _print_appended, _print_recent
from tool.runtime_logging import (
    DailyFileHandler,
    _console_python_executable,
    format_json_for_log,
)


class RuntimeLoggingTests(unittest.TestCase):
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

    def test_json_log_keeps_payload_and_compacts_base64_images(self) -> None:
        image = "a" * 2_048
        output = format_json_for_log(
            {
                "model": "vision-model",
                "messages": [{"images": [image]}],
                "api_key": "do-not-log-this",
            }
        )

        self.assertIn('"model": "vision-model"', output)
        self.assertIn("数据已省略", output)
        self.assertIn("字符数=2048", output)
        self.assertNotIn(image, output)
        self.assertNotIn("do-not-log-this", output)

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


if __name__ == "__main__":
    unittest.main()
