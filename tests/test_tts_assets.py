from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tool.tts_assets import (
    configure_local_tts_weights,
    locate_gpt_sovits_root,
    locate_murasame_weights,
    locate_tts_assets,
    tts_service_is_reachable,
)


class TTSAssetTests(unittest.TestCase):
    def test_reachability_uses_openapi_without_calling_tts(self) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {"paths": {"/tts": {}}}
        with patch(
            "requests.Session.get",
            return_value=response,
        ) as get:
            self.assertTrue(
                tts_service_is_reachable(
                    "http://127.0.0.1:9880/tts"
                )
            )
        self.assertEqual(
            get.call_args.args[0],
            "http://127.0.0.1:9880/openapi.json",
        )

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
            references = self._create_references(model)

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
            self.assertEqual(state.reference_root, references.resolve())
            self.assertTrue(state.reference_voices_ready)

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

    def test_configured_paths_do_not_fall_back_to_managed_defaults(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            configured_engine = root / "missing-engine"
            configured_model = root / "missing-model"
            managed_engine = root / "managed-engine"
            managed_engine.mkdir()
            (managed_engine / "api_v2.py").write_text("", encoding="utf-8")
            managed_model = root / "managed-model"
            managed_model.mkdir()
            (managed_model / "murasame-gpt.ckpt").write_bytes(b"gpt")
            (managed_model / "murasame-sovits.pth").write_bytes(b"sovits")

            with (
                patch(
                    "tool.tts_assets.managed_gpt_sovits_dir",
                    return_value=managed_engine,
                ),
                patch(
                    "tool.tts_assets.managed_tts_model_dir",
                    return_value=managed_model,
                ),
                patch("tool.tts_assets.MIN_GPT_WEIGHT_SIZE", 1),
                patch("tool.tts_assets.MIN_SOVITS_WEIGHT_SIZE", 1),
            ):
                self.assertIsNone(
                    locate_gpt_sovits_root(str(configured_engine))
                )
                self.assertEqual(
                    locate_murasame_weights(
                        configured_model_dir=str(configured_model)
                    ),
                    (None, None),
                )

    def test_empty_paths_check_only_managed_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            engine = root / "engine"
            engine.mkdir()
            (engine / "api_v2.py").write_text("", encoding="utf-8")
            model = root / "model"
            model.mkdir()
            gpt = model / "murasame-gpt.ckpt"
            sovits = model / "murasame-sovits.pth"
            gpt.write_bytes(b"gpt")
            sovits.write_bytes(b"sovits")

            with (
                patch(
                    "tool.tts_assets.managed_gpt_sovits_dir",
                    return_value=engine,
                ),
                patch(
                    "tool.tts_assets.managed_tts_model_dir",
                    return_value=model,
                ),
                patch("tool.tts_assets.MIN_GPT_WEIGHT_SIZE", 1),
                patch("tool.tts_assets.MIN_SOVITS_WEIGHT_SIZE", 1),
            ):
                self.assertEqual(
                    locate_gpt_sovits_root(),
                    engine.resolve(),
                )
                self.assertEqual(
                    locate_murasame_weights(),
                    (gpt.resolve(), sovits.resolve()),
                )

    @staticmethod
    def _create_references(model: Path) -> Path:
        root = model / "reference_voices"
        for emotion in ("平静", "高兴", "害羞", "生气", "惊讶", "着急"):
            directory = root / emotion
            directory.mkdir(parents=True)
            (directory / "asr.txt").write_text(
                "reference transcript",
                encoding="utf-8",
            )
            (directory / "ref.wav").write_bytes(b"RIFF")
        return root


if __name__ == "__main__":
    unittest.main()
