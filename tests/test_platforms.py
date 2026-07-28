from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from aipet.core.config import AppSettings, TTSSettings, load_settings, save_settings
from aipet.platforms import CredentialError, get_platform_runtime
from aipet.platforms.macos import create_runtime as create_macos_runtime
from aipet.platforms.macos.credentials import KeychainStore
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
        self.assertTrue(callable(runtime.paths.user_data_dir))
        self.assertTrue(callable(runtime.windowing.ensure_topmost))
        self.assertTrue(callable(runtime.input.create_voice_trigger))
        self.assertTrue(callable(runtime.credentials.protect))
        self.assertTrue(callable(runtime.processes.hidden_subprocess_options))
        self.assertTrue(callable(runtime.archives.seven_zip_candidates))
        self.assertTrue(callable(runtime.audio.prepare_input_devices))

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
        self.assertFalse(runtime.capabilities.window_topmost)
        self.assertTrue(runtime.capabilities.secure_credentials)
        self.assertTrue(callable(runtime.paths.user_data_dir))
        self.assertTrue(callable(runtime.windowing.ensure_topmost))
        self.assertTrue(callable(runtime.input.create_voice_trigger))
        self.assertTrue(callable(runtime.credentials.protect))
        self.assertTrue(callable(runtime.processes.hidden_subprocess_options))
        self.assertTrue(callable(runtime.archives.seven_zip_candidates))
        self.assertTrue(callable(runtime.audio.prepare_input_devices))

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
