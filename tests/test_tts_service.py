from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from aipet.core.config import TTSSettings
from aipet.core.tts_assets import TTSAssetState, TTSHealthCheck
from aipet.core.tts_service import (
    LocalTTSServiceManager,
    TTSServiceError,
    _build_start_command,
)


class TTSServiceTests(unittest.TestCase):
    @unittest.skipUnless(
        sys.platform == "win32",
        "A bundled runtime/python.exe layout only exists in the Windows "
        "build; the macOS adapter installs an isolated .venv instead",
    )
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

    @unittest.skipUnless(
        sys.platform == "win32",
        "A bundled runtime/python.exe layout only exists in the Windows "
        "build; the macOS adapter installs an isolated .venv instead",
    )
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
                        "aipet.core.tts_service.probe_tts_service",
                        side_effect=[
                            TTSHealthCheck(False, "connection refused"),
                            TTSHealthCheck(
                                True,
                                "OpenAPI confirmed POST /tts",
                                200,
                            ),
                        ],
                    ),
                    patch(
                        "aipet.core.tts_service.tts_service_is_reachable",
                        side_effect=[False, True],
                    ),
                    patch.object(manager._process_job, "assign"),
                    patch(
                        "aipet.core.tts_service.subprocess.Popen",
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
                "aipet.core.tts_service.probe_tts_service",
                return_value=TTSHealthCheck(False, "connection refused"),
            ),
            patch(
                "aipet.core.tts_service.tts_service_is_reachable",
                return_value=False,
            ),
            self.assertRaises(TTSServiceError),
        ):
            manager.ensure_running(settings)

    def test_autodl_starts_ssh_tunnel_and_remote_command(self) -> None:
        manager = LocalTTSServiceManager()
        settings = TTSSettings(
            backend="autodl",
            base_url="http://127.0.0.1:9880/tts",
            autodl_ssh_command=(
                "ssh -p 12345 root@connect.example.com"
            ),
            autodl_remote_command="bash -lc 'bash run.sh; bash'",
            autodl_password_encrypted="encrypted",
            timeout_seconds=10,
        )
        connection = Mock()
        connection.is_active.return_value = True
        with (
            patch(
                "aipet.core.tts_service.probe_tts_service",
                return_value=TTSHealthCheck(False, "connection refused"),
            ),
            patch(
                "aipet.core.tts_service.tts_service_is_reachable",
                side_effect=[False, True],
            ),
            patch(
                "aipet.core.tts_service.AutoDLTTSConnection",
                return_value=connection,
            ),
            patch(
                "aipet.core.tts_service.unprotect_secret",
                return_value="secret",
            ),
        ):
            self.assertTrue(manager.ensure_running(settings))

        connection.start.assert_called_once_with(
            settings.autodl_ssh_command,
            "secret",
            settings.autodl_remote_command,
            local_address=("127.0.0.1", 9880),
            remote_address=("127.0.0.1", 9880),
            progress=None,
        )
        self.assertTrue(manager.stop())
        connection.stop.assert_called_once_with()

    def test_autodl_rejects_unowned_service_on_tunnel_port(self) -> None:
        manager = LocalTTSServiceManager()
        settings = TTSSettings(
            backend="autodl",
            base_url="http://127.0.0.1:9880/tts",
        )
        with (
            patch(
                "aipet.core.tts_service.probe_tts_service",
                return_value=TTSHealthCheck(
                    True,
                    "OpenAPI confirmed POST /tts",
                    200,
                ),
            ),
            self.assertRaisesRegex(
                TTSServiceError,
                "not started through the current AutoDL SSH session",
            ),
        ):
            manager.ensure_running(settings)

    def test_shutdown_closes_process_lifetime_job(self) -> None:
        manager = LocalTTSServiceManager()
        with patch.object(manager._process_job, "close") as close:
            manager.shutdown()
        close.assert_called_once_with()

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
