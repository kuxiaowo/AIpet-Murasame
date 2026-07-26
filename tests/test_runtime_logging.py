from __future__ import annotations

import io
import logging
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from tool.log_viewer import _print_appended, _print_recent
from tool.runtime_logging import DailyFileHandler


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


if __name__ == "__main__":
    unittest.main()
