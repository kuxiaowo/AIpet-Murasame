from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from aipet.core.config import AppSettings, TTSSettings, load_settings, save_settings
from aipet.platforms import CredentialError, get_platform_runtime
from aipet.platforms.macos import create_runtime as create_macos_runtime
from aipet.platforms.macos.credentials import KeychainStore
from aipet.platforms.macos.tts_bootstrap import MacOSTTSBootstrap
from aipet.platforms.registry import reset_platform_runtime_for_tests
from aipet.platforms.windows import create_runtime as create_windows_runtime
from aipet.platforms.windows.processes import WindowsKillOnCloseJob


class PlatformArchitectureTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_platform_runtime_for_tests()

    def test_windows_runtime_exposes_every_platform_policy(self) -> None:
        runtime = create_windows_runtime()

        self.assertEqual(runtime.platform_id, "windows")
        self.assertTrue(runtime.capabilities.window_topmost)
        self.assertTrue(runtime.capabilities.secure_credentials)
        self.assertFalse(runtime.capabilities.managed_tts_bootstrap)
        self.assertTrue(callable(runtime.paths.user_data_dir))
        self.assertTrue(callable(runtime.windowing.ensure_topmost))
        self.assertTrue(callable(runtime.input.create_voice_trigger))
        self.assertEqual(runtime.input.voice_trigger_shortcut(), "Caps Lock")
        self.assertTrue(callable(runtime.credentials.protect))
        self.assertTrue(callable(runtime.processes.hidden_subprocess_options))
        self.assertTrue(callable(runtime.archives.seven_zip_candidates))
        self.assertTrue(callable(runtime.audio.prepare_input_devices))
        self.assertTrue(callable(runtime.tts_bootstrap.install))

    def test_windows_archive_policy_selects_expected_engine(self) -> None:
        archives = create_windows_runtime().archives

        standard = archives.select_tts_engine_archive(
            ["NVIDIA GeForce RTX 4090"]
        )
        nvidia50 = archives.select_tts_engine_archive(
            ["NVIDIA GeForce RTX 5080"]
        )

        self.assertNotEqual(standard.filename, nvidia50.filename)
        self.assertIn("nvidia50", nvidia50.filename)
        self.assertGreater(standard.size, 0)
        self.assertEqual(len(standard.sha256), 64)

    def test_windows_process_policy_preserves_console_modes(self) -> None:
        policy = create_windows_runtime().processes
        startupinfo = Mock(dwFlags=0)
        with (
            patch(
                "aipet.platforms.windows.processes.subprocess.STARTUPINFO",
                return_value=startupinfo,
                create=True,
            ),
            patch(
                "aipet.platforms.windows.processes.subprocess.STARTF_USESHOWWINDOW",
                1,
                create=True,
            ),
            patch(
                "aipet.platforms.windows.processes.subprocess.CREATE_NO_WINDOW",
                2,
                create=True,
            ),
            patch(
                "aipet.platforms.windows.processes.subprocess.CREATE_NEW_CONSOLE",
                4,
                create=True,
            ),
        ):
            hidden = policy.hidden_subprocess_options()
            console = policy.new_console_subprocess_options()

        self.assertIn("startupinfo", hidden)
        self.assertNotEqual(hidden["creationflags"], 0)
        self.assertNotEqual(console["creationflags"], 0)
        self.assertIsInstance(
            policy.create_child_process_guard(),
            WindowsKillOnCloseJob,
        )

    def test_windows_idle_policy_handles_api_failure(self) -> None:
        runtime = create_windows_runtime()
        fake_windll = Mock()
        fake_windll.user32.GetLastInputInfo.return_value = 0

        with patch(
            "aipet.platforms.windows.runtime.ctypes.windll",
            fake_windll,
            create=True,
        ):
            self.assertEqual(runtime.input.idle_seconds(), 0.0)

    def test_windows_voice_factory_uses_platform_implementation(self) -> None:
        fake_module = types.ModuleType(
            "aipet.platforms.windows.voice_trigger"
        )
        fake_trigger = Mock()
        fake_module.CapslockVoiceTrigger = fake_trigger

        with patch.dict(
            sys.modules,
            {"aipet.platforms.windows.voice_trigger": fake_module},
        ):
            result = create_windows_runtime().input.create_voice_trigger(
                on_text_ready=Mock()
            )

        self.assertIs(result, fake_trigger.return_value)
        fake_trigger.assert_called_once()

    def test_macos_runtime_exposes_every_platform_policy(self) -> None:
        runtime = create_macos_runtime()

        self.assertEqual(runtime.platform_id, "macos")
        self.assertTrue(runtime.capabilities.window_topmost)
        self.assertTrue(runtime.capabilities.secure_credentials)
        self.assertTrue(runtime.capabilities.managed_tts_bootstrap)
        self.assertTrue(callable(runtime.paths.user_data_dir))
        self.assertTrue(callable(runtime.windowing.ensure_topmost))
        self.assertTrue(callable(runtime.input.create_voice_trigger))
        self.assertEqual(runtime.input.voice_trigger_shortcut(), "Option+V")
        self.assertTrue(callable(runtime.credentials.protect))
        self.assertTrue(callable(runtime.processes.hidden_subprocess_options))
        self.assertTrue(callable(runtime.archives.seven_zip_candidates))
        self.assertTrue(callable(runtime.audio.prepare_input_devices))
        self.assertTrue(callable(runtime.tts_bootstrap.install))

        with patch.object(sys, "platform", "darwin"):
            reset_platform_runtime_for_tests()
            self.assertEqual(get_platform_runtime().platform_id, "macos")

    def test_macos_idle_policy_parses_ioreg_output(self) -> None:
        runtime = create_macos_runtime()
        result = Mock(stdout='"HIDIdleTime" = 3000000000')

        with patch(
            "aipet.platforms.macos.runtime.subprocess.run",
            return_value=result,
        ):
            self.assertEqual(runtime.input.idle_seconds(), 3.0)

    @patch(
        "aipet.platforms.macos.windowing._ObjectiveCRuntime"
    )
    def test_macos_window_joins_fullscreen_spaces(self, runtime_class) -> None:
        native = runtime_class.return_value
        native.object_result.return_value = 321
        from aipet.platforms.macos.windowing import configure_native_window

        self.assertTrue(configure_native_window(123))
        native.set_integer.assert_any_call(
            321,
            "setCollectionBehavior:",
            (1 << 0) | (1 << 8),
        )
        native.set_integer.assert_any_call(321, "setLevel:", 25)

    @patch("aipet.platforms.macos.runtime.KeychainStore")
    def test_macos_uses_keychain_credentials(self, keychain_store) -> None:
        runtime = create_macos_runtime()
        self.assertIs(runtime.credentials, keychain_store.return_value)

    def test_macos_keychain_adds_missing_password(self) -> None:
        store = KeychainStore.__new__(KeychainStore)
        store._security = Mock()
        store._security.SecKeychainAddGenericPassword.return_value = 0
        store._core_foundation = Mock()
        with patch.object(store, "_find", return_value=-25300):
            token = store.protect("secret")
        self.assertEqual(token, "macos-keychain:autodl")
        store._security.SecKeychainAddGenericPassword.assert_called_once()

    def test_macos_download_manager_imports_without_managed_archive(
        self,
    ) -> None:
        from aipet.core import download_manager

        self.assertEqual(download_manager.TTS_ENGINE_ARCHIVE, "")

    def test_macos_tts_runtime_accepts_sibling_virtualenv(self) -> None:
        root = Path("/tmp/models/tts/GPT-SoVITS")
        candidates = (
            create_macos_runtime()
            .processes.runtime_python_candidates(root)
        )
        self.assertIn(
            root.parent / ".gpt-sovits-venv" / "bin" / "python",
            candidates,
        )

    def test_macos_tts_bootstrap_checks_base_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            required = (
                "GPT_SoVITS/pretrained_models/"
                "chinese-roberta-wwm-ext-large/pytorch_model.bin",
                "GPT_SoVITS/pretrained_models/"
                "chinese-hubert-base/pytorch_model.bin",
                "GPT_SoVITS/pretrained_models/"
                "gsv-v4-pretrained/vocoder.pth",
            )
            for relative in required:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()

            self.assertTrue(MacOSTTSBootstrap._base_assets_ready(root))

    def test_macos_tts_bootstrap_uses_certifi_for_downloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            response = MagicMock()
            response.read.side_effect = (b"data", b"")
            request = MagicMock()
            request.__enter__.return_value = response
            with (
                patch(
                    "aipet.platforms.macos.tts_bootstrap.certifi.where",
                    return_value="/tmp/cacert.pem",
                ),
                patch(
                    "aipet.platforms.macos.tts_bootstrap.ssl.create_default_context",
                    return_value="trusted-context",
                ),
                patch(
                    "aipet.platforms.macos.tts_bootstrap.urlopen",
                    return_value=request,
                ) as open_url,
            ):
                MacOSTTSBootstrap._download(
                    "https://example.invalid/model.zip",
                    Path(directory) / "model.zip",
                )

            self.assertEqual(
                open_url.call_args.kwargs["context"],
                "trusted-context",
            )
            self.assertEqual((Path(directory) / "model.zip").read_bytes(), b"data")

    def test_macos_tts_bootstrap_reports_download_speed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            response = MagicMock()
            response.read.side_effect = (b"x" * 1024**2, b"")
            request = MagicMock()
            request.__enter__.return_value = response
            updates: list[str] = []
            with (
                patch(
                    "aipet.platforms.macos.tts_bootstrap.urlopen",
                    return_value=request,
                ),
                patch(
                    "aipet.platforms.macos.tts_bootstrap.time.monotonic",
                    side_effect=(0.0, 1.0, 1.0),
                ),
            ):
                MacOSTTSBootstrap._download(
                    "https://example.invalid/model.zip",
                    Path(directory) / "model.zip",
                    progress=updates.append,
                    label="model.zip",
                )

            self.assertIn("MB/s", updates[-1])

    def test_macos_tts_bootstrap_finds_packaged_uv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            contents = Path(directory) / "Contents"
            executable = contents / "MacOS" / "AIpet-Murasame"
            uv = contents / "Frameworks" / "tools" / "uv"
            executable.parent.mkdir(parents=True)
            executable.touch()
            uv.parent.mkdir(parents=True)
            uv.touch(mode=0o755)

            with (
                patch.dict("os.environ", {}, clear=True),
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "executable", str(executable)),
            ):
                self.assertEqual(MacOSTTSBootstrap._uv(), uv.resolve())

    def test_macos_tts_bootstrap_replaces_empty_engine_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "GPT-SoVITS"
            root.mkdir()
            bootstrap = MacOSTTSBootstrap()

            def clone(command, **_kwargs) -> None:
                staging = Path(command[-1])
                staging.mkdir()
                (staging / "api_v2.py").touch()

            with (
                patch.object(bootstrap, "_run", side_effect=clone),
                patch.object(bootstrap, "_output", return_value=(
                    "d7c2210da8c013e81a94bfc7b811a477c99fd506"
                )),
            ):
                bootstrap._install_source(root, lambda _stage: None)

            self.assertTrue((root / "api_v2.py").is_file())

    def test_configuration_round_trip_preserves_autodl_fields(self) -> None:
        original = AppSettings(
            tts=TTSSettings(
                enabled=True,
                backend="autodl",
                autodl_ssh_command="ssh -p 1234 root@example",
                autodl_remote_command="bash start.sh",
                autodl_remote_reference_root="/root/custom",
                autodl_password_encrypted="encrypted",
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            save_settings(original, path)
            loaded = load_settings(path)

        self.assertEqual(loaded, original)

    def test_shared_packages_do_not_contain_platform_branches(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        sources = [
            *(project_root / "aipet" / "core").glob("*.py"),
            *(project_root / "aipet" / "ui").glob("*.py"),
            project_root / "aipet" / "application.py",
        ]
        forbidden = (
            "sys.platform",
            "os.name",
            "ctypes.",
            "ctypes import",
            "import ctypes",
        )
        violations: list[str] = []
        for source in sources:
            content = source.read_text(encoding="utf-8")
            for marker in forbidden:
                if marker in content:
                    violations.append(f"{source.name}: {marker}")
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
