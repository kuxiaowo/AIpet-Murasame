from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tool.whisper_models import (
    WHISPER_MODELS,
    find_local_model,
    model_page_url,
    model_repository,
)


class WhisperModelTests(unittest.TestCase):
    def test_builtin_models_and_repository_urls(self) -> None:
        self.assertIn("large-v3", WHISPER_MODELS)
        self.assertIn("turbo", WHISPER_MODELS)
        self.assertEqual(
            model_repository("large-v3"),
            "Systran/faster-whisper-large-v3",
        )
        self.assertEqual(
            model_page_url("large-v3"),
            "https://huggingface.co/Systran/faster-whisper-large-v3",
        )

    def test_existing_local_directory_is_detected_without_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            expected = str(Path(directory).resolve())
            self.assertEqual(find_local_model(directory), expected)


if __name__ == "__main__":
    unittest.main()
