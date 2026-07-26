from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tool.config import TTSSettings
from tool.tts_assets import TTSAssetState
from tool.tts_service import (
    LocalTTSServiceManager,
    TTSServiceError,
    _build_start_command,
)


class TTSServiceTests(unittest.TestCase):
    def test_build_command_prefers_bundled_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            engine = self._create_engine(Path(directory))
            command, environment = _build_start_command(
                engine,
                ("127.0.0.1", 9880),
            )

            self.assertEqual(
                Path(command[0]),
                (engine / "runtime" / "python.exe").resolve(),
            )
            self.assertEqual(Path(command[1]), engine / "api_v2.py")
            self.assertEqual(command[-4:], ["-p", "9880", "-c", command[-1]])
            self.assertEqual(
                Path(command[-1]),
                engine / "GPT_SoVITS" / "configs" / "tts_infer.yaml",
            )
            self.assertTrue(
                environment["PATH"].startswith(str(engine / "runtime"))
            )

    def test_build_command_requires_engine_python_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            engine = self._create_engine(Path(directory))
            (engine / "runtime" / "python.exe").unlink()

            with self.assertRaisesRegex(
                TTSServiceError,
                "does not contain a bundled Python runtime",
            ):
                _build_start_command(engine, ("127.0.0.1", 9880))

    def test_ensure_running_launches_once_and_stop_only_owned_process(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = self._create_engine(root / "engine")
            state = TTSAssetState(
                engine_root=engine,
                engine_ready=True,
                gpt_weight=root / "gpt.ckpt",
                sovits_weight=root / "sovits.pth",
                reference_root=root / "references",
                reference_voices_ready=True,
            )
            settings = TTSSettings(
                enabled=True,
                engine_root=str(engine),
                base_url="http://127.0.0.1:9880/tts",
                timeout_seconds=10,
            )
            process = Mock(spec=subprocess.Popen)
            process.poll.return_value = None
            process.wait.return_value = 0
            previous = os.environ.get("AIPET_DATA_DIR")
            os.environ["AIPET_DATA_DIR"] = str(root / "data")
            manager = LocalTTSServiceManager()
            try:
                with (
                    patch(
                        "tool.tts_service.tts_service_is_reachable",
                        side_effect=[False, False, True, True],
                    ),
                    patch(
                        "tool.tts_service.subprocess.Popen",
                        return_value=process,
                    ) as popen,
                ):
                    started = manager.ensure_running(settings, state=state)
                    started_again = manager.ensure_running(
                        settings,
                        state=state,
                    )

                self.assertTrue(started)
                self.assertFalse(started_again)
                self.assertTrue(manager.owns_running_process())
                self.assertEqual(popen.call_count, 1)
                self.assertTrue(manager.stop())
                process.terminate.assert_called_once_with()
                self.assertFalse(manager.owns_running_process())
                self.assertFalse(manager.stop())
            finally:
                manager.shutdown()
                if previous is None:
                    os.environ.pop("AIPET_DATA_DIR", None)
                else:
                    os.environ["AIPET_DATA_DIR"] = previous

    def test_remote_endpoint_is_never_started(self) -> None:
        manager = LocalTTSServiceManager()
        settings = TTSSettings(base_url="https://example.com/tts")
        with (
            patch(
                "tool.tts_service.tts_service_is_reachable",
                return_value=False,
            ),
            self.assertRaises(TTSServiceError),
        ):
            manager.ensure_running(settings)

    @staticmethod
    def _create_engine(root: Path) -> Path:
        (root / "runtime").mkdir(parents=True)
        (root / "runtime" / "python.exe").write_bytes(b"runtime")
        (root / "api_v2.py").write_text("# api", encoding="utf-8")
        config = root / "GPT_SoVITS" / "configs" / "tts_infer.yaml"
        config.parent.mkdir(parents=True)
        config.write_text("custom: {}", encoding="utf-8")
        return root.resolve()


if __name__ == "__main__":
    unittest.main()
