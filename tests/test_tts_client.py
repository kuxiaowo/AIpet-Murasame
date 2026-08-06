from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from aipet.core.config import AppSettings
from aipet.core.tts import TTSClient, TTSError
from aipet.core.tts_assets import TTSAssetState


class TTSClientDiagnosticsTests(unittest.TestCase):
    def test_http_error_logs_and_exposes_server_response(self) -> None:
        response = Mock(spec=requests.Response)
        response.status_code = 400
        response.headers = {"Content-Type": "application/json"}
        response.text = (
            '{"message":"tts failed",'
            '"Exception":"reference audio was not found"}'
        )
        response.raise_for_status.side_effect = requests.HTTPError(
            "400 Client Error",
            response=response,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference_root = root / "reference_voices"
            reference_dir = reference_root / "平静"
            reference_dir.mkdir(parents=True)
            (reference_dir / "asr.txt").write_text(
                "reference transcript",
                encoding="utf-8",
            )
            (reference_dir / "ref.wav").write_bytes(b"RIFF-reference")
            state = TTSAssetState(
                engine_root=root / "engine",
                engine_ready=True,
                gpt_weight=root / "murasame-gpt.ckpt",
                sovits_weight=root / "murasame-sovits.pth",
                reference_root=reference_root,
                reference_voices_ready=True,
            )
            settings = AppSettings()
            settings.tts.enabled = True

            client = TTSClient(settings)
            client.session = Mock()
            client.session.post.return_value = response
            with (
                patch(
                    "aipet.core.tts.locate_tts_assets",
                    return_value=state,
                ),
                patch("aipet.core.tts.get_tts_service_manager"),
                patch("aipet.core.tts.configure_local_tts_weights"),
                self.assertLogs("aipet.tts", level="WARNING") as captured,
                self.assertRaises(TTSError) as raised,
            ):
                client.synthesize("こんにちは", "平静")

        message = str(raised.exception)
        self.assertIn("HTTP 400", message)
        self.assertRegex(message, r"\[ID=[0-9a-f]{8}\]")
        self.assertIn("reference audio was not found", message)
        joined_logs = "\n".join(captured.output)
        self.assertIn("TTS 合成请求被拒绝", joined_logs)
        self.assertRegex(joined_logs, r"ID=[0-9a-f]{8}")
        self.assertIn("Content-Type=application/json", joined_logs)
        self.assertIn("reference audio was not found", joined_logs)

    def test_response_summary_truncates_large_error_body(self) -> None:
        response = Mock(spec=requests.Response)
        response.status_code = 500
        response.headers = {"Content-Type": "text/plain"}
        response.text = "x" * 2_100
        response.raise_for_status.side_effect = requests.HTTPError(
            "500 Server Error",
            response=response,
        )

        settings = AppSettings()
        settings.tts.enabled = True
        settings.tts.backend = "autodl"
        client = TTSClient(settings)
        client.session = Mock()
        client.session.post.return_value = response
        manager = Mock()
        manager.autodl_reference.return_value = (
            "/root/reference_voices/平静/ref.wav",
            "reference transcript",
        )

        with (
            patch(
                "aipet.core.tts.get_tts_service_manager",
                return_value=manager,
            ),
            self.assertLogs("aipet.tts", level="WARNING"),
            self.assertRaises(TTSError) as raised,
        ):
            client.synthesize("こんにちは", "平静")

        self.assertIn("已截断 100 字符", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
