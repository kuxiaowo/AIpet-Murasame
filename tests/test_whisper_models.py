from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tool.stt import clear_model_cache, transcribe_full
from tool.whisper_models import (
    WHISPER_MODELS,
    find_local_model,
    looks_like_local_model_path,
    model_page_url,
    model_repository,
)


class WhisperModelTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_model_cache()

    def tearDown(self) -> None:
        clear_model_cache()

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
            root = Path(directory)
            (root / "model.bin").write_bytes(b"model")
            (root / "config.json").write_text("{}", encoding="utf-8")
            expected = str(Path(directory).resolve())
            self.assertEqual(find_local_model(directory), expected)

    def test_empty_local_directory_is_not_treated_as_a_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(find_local_model(directory))
            self.assertTrue(looks_like_local_model_path(directory))

    def test_named_model_checks_only_managed_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            managed = root / "managed"
            managed.mkdir()
            files = {
                "model.bin": b"model",
                "config.json": b"{}",
            }
            for name, content in files.items():
                (managed / name).write_bytes(content)
            (managed / ".aipet-download.json").write_text(
                json.dumps(
                    {
                        "files": [
                            {"path": name, "size": len(content)}
                            for name, content in files.items()
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "tool.whisper_models.managed_whisper_dir",
                return_value=managed,
            ):
                self.assertEqual(
                    find_local_model("large-v3"),
                    str(managed.resolve()),
                )
            self.assertEqual(
                find_local_model("large-v3", str(managed)),
                str(managed.resolve()),
            )

    def test_missing_named_model_does_not_search_other_caches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "managed"
            with patch(
                "tool.whisper_models.managed_whisper_dir",
                return_value=missing,
            ):
                self.assertIsNone(find_local_model("large-v3"))

    def test_transcription_never_falls_back_to_model_name(self) -> None:
        whisper_model = Mock()
        module = SimpleNamespace(WhisperModel=whisper_model)
        with (
            patch.dict(sys.modules, {"faster_whisper": module}),
            patch("tool.stt.find_local_model", return_value=None),
            self.assertRaisesRegex(RuntimeError, "configured model directory"),
        ):
            transcribe_full("audio.wav", model_size="large-v3")
        whisper_model.assert_not_called()

    def test_auto_device_falls_back_when_lazy_cuda_inference_fails(
        self,
    ) -> None:
        def failing_segments():
            raise RuntimeError("cublas64_12.dll is missing")
            yield

        cuda_model = Mock()
        cuda_model.transcribe.return_value = (failing_segments(), None)
        cpu_model = Mock()
        cpu_model.transcribe.return_value = (
            iter([SimpleNamespace(text="识别成功")]),
            None,
        )
        whisper_model = Mock(side_effect=[cuda_model, cpu_model])
        module = SimpleNamespace(WhisperModel=whisper_model)

        with (
            patch.dict(sys.modules, {"faster_whisper": module}),
            patch(
                "tool.stt.find_local_model",
                return_value="C:/models/whisper",
            ),
        ):
            result = transcribe_full("audio.wav", device="auto")
            cpu_model.transcribe.return_value = (
                iter([SimpleNamespace(text="识别成功")]),
                None,
            )
            second_result = transcribe_full("second.wav", device="auto")

        self.assertEqual(result, "识别成功")
        self.assertEqual(
            [call.kwargs["device"] for call in whisper_model.call_args_list],
            ["cuda", "cpu"],
        )
        self.assertEqual(second_result, "识别成功")
        self.assertEqual(whisper_model.call_count, 2)
        self.assertEqual(cpu_model.transcribe.call_count, 2)

    def test_loaded_model_is_reused_for_later_transcriptions(self) -> None:
        model = Mock()
        model.transcribe.side_effect = [
            (iter([SimpleNamespace(text="第一次")]), None),
            (iter([SimpleNamespace(text="第二次")]), None),
        ]
        whisper_model = Mock(return_value=model)
        module = SimpleNamespace(WhisperModel=whisper_model)

        with (
            patch.dict(sys.modules, {"faster_whisper": module}),
            patch(
                "tool.stt.find_local_model",
                return_value="C:/models/whisper",
            ),
        ):
            first = transcribe_full("first.wav", device="cuda")
            second = transcribe_full("second.wav", device="cuda")

        self.assertEqual(first, "第一次")
        self.assertEqual(second, "第二次")
        whisper_model.assert_called_once_with(
            "C:/models/whisper",
            device="cuda",
            compute_type="float16",
        )
        self.assertEqual(model.transcribe.call_count, 2)


if __name__ == "__main__":
    unittest.main()
