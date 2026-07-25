from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tool.tts_assets import configure_local_tts_weights, locate_tts_assets


class TTSAssetTests(unittest.TestCase):
    def test_locates_configured_engine_and_voice_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = root / "GPT-SoVITS"
            engine.mkdir()
            (engine / "api_v2.py").write_text("", encoding="utf-8")
            model = root / "voice"
            model.mkdir()
            (model / "murasame-gpt.ckpt").write_bytes(b"gpt")
            (model / "murasame-sovits.pth").write_bytes(b"sovits")

            with (
                patch("tool.tts_assets.MIN_GPT_WEIGHT_SIZE", 1),
                patch("tool.tts_assets.MIN_SOVITS_WEIGHT_SIZE", 1),
            ):
                state = locate_tts_assets(
                    configured_engine_root=str(engine),
                    configured_model_dir=str(model),
                )

            self.assertEqual(state.engine_root, engine.resolve())
            self.assertFalse(state.engine_ready)
            self.assertTrue(state.model_ready)
            self.assertEqual(state.model_directory, model.resolve())

            response = Mock()
            response.raise_for_status.return_value = None
            with patch("requests.Session.get", return_value=response) as get:
                configure_local_tts_weights(
                    "http://127.0.0.1:9880/tts",
                    state,
                    30,
                )
            self.assertEqual(get.call_count, 2)
            self.assertTrue(
                get.call_args_list[0].args[0].endswith(
                    "/set_gpt_weights"
                )
            )
            self.assertTrue(
                get.call_args_list[1].args[0].endswith(
                    "/set_sovits_weights"
                )
            )


if __name__ == "__main__":
    unittest.main()
