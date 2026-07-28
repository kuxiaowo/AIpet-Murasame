from __future__ import annotations

import hashlib
import http.server
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from classes.download_manager import (
    BUNDLED_7ZIP,
    TTS_ENGINE_ARCHIVE,
    TTS_ENGINE_ARCHIVE_NVIDIA50,
    TTS_REFERENCE_MODEL,
    AssetDownloadWorker,
    DownloadManager,
    RemoteFile,
    _activate_extracted_engine,
    _extract_gpt_sovits_archive,
    _find_7zip,
    _sha256,
    _tts_files,
    select_tts_engine_archive,
)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass


class DownloadWorkerTests(unittest.TestCase):
    def test_manager_uses_explicit_download_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = DownloadManager()
            with patch.object(manager, "_start") as start:
                manager.start_whisper(
                    "large-v3",
                    root / "whisper-model",
                )
                self.assertEqual(
                    start.call_args.args[3],
                    root / "whisper-model",
                )

                manager.start_tts(
                    root / "voice-model",
                    include_engine=True,
                    engine_destination=root / "GPT-SoVITS",
                )
                self.assertEqual(
                    start.call_args.args[3],
                    root / "voice-model",
                )
                self.assertEqual(
                    start.call_args.kwargs["tts_engine_destination"],
                    root / "GPT-SoVITS",
                )

    def test_finds_7zip_before_bsdtar_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "7z.exe"
            executable.write_bytes(b"7z")
            missing_bundled = Path(directory) / "missing-7zr.exe"
            with (
                patch(
                    "classes.download_manager.BUNDLED_7ZIP",
                    missing_bundled,
                ),
                patch(
                    "classes.download_manager.shutil.which",
                    side_effect=lambda name: (
                        str(executable) if name == "7z" else None
                    ),
                ),
            ):
                self.assertEqual(_find_7zip(), executable.resolve())

    def test_prefers_bundled_7zip(self) -> None:
        self.assertTrue(BUNDLED_7ZIP.is_file())
        with patch(
            "classes.download_manager.shutil.which",
            side_effect=AssertionError("PATH lookup should not win"),
        ):
            self.assertEqual(_find_7zip(), BUNDLED_7ZIP.resolve())

    def test_hash_reports_progress(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.bin"
            path.write_bytes(b"x" * (2 * 1024 * 1024 + 5))
            progress: list[int] = []

            _sha256(path, progress.append)

            self.assertTrue(progress)
            self.assertEqual(progress[-1], path.stat().st_size)

    def test_atomically_replaces_managed_engine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "staging" / "GPT-SoVITS"
            source.mkdir(parents=True)
            (source / "api_v2.py").write_text("new", encoding="utf-8")
            destination = root / "GPT-SoVITS"
            destination.mkdir()
            (destination / "api_v2.py").write_text(
                "old",
                encoding="utf-8",
            )
            stages: list[str] = []

            _activate_extracted_engine(
                source,
                destination,
                lambda stage, _done, _total, _current: stages.append(
                    stage
                ),
            )

            self.assertEqual(
                (destination / "api_v2.py").read_text(encoding="utf-8"),
                "new",
            )
            self.assertFalse(source.exists())
            self.assertIn("installing", stages)
            self.assertIn("cleaning", stages)
            self.assertFalse(
                any(root.glob(".GPT-SoVITS-backup-*"))
            )

    def test_selects_engine_archive_for_gpu_generation(self) -> None:
        self.assertEqual(
            select_tts_engine_archive(["NVIDIA GeForce RTX 5070 Ti"]),
            TTS_ENGINE_ARCHIVE_NVIDIA50,
        )
        self.assertEqual(
            select_tts_engine_archive(["NVIDIA GeForce RTX 4090"]),
            TTS_ENGINE_ARCHIVE,
        )
        self.assertEqual(
            select_tts_engine_archive(
                ["NVIDIA RTX 5000 Ada Generation"],
            ),
            TTS_ENGINE_ARCHIVE,
        )
        self.assertEqual(
            select_tts_engine_archive([]),
            TTS_ENGINE_ARCHIVE,
        )

    def test_tts_download_includes_selected_engine_archive(self) -> None:
        with patch(
            "classes.download_manager.detect_nvidia_gpu_names",
            return_value=["NVIDIA GeForce RTX 5080"],
        ):
            files = _tts_files(include_engine=True)

        archives = [
            item for item in files if item.relative_path.endswith(".7z")
        ]
        self.assertEqual(len(archives), 1)
        self.assertEqual(
            Path(archives[0].relative_path).name,
            TTS_ENGINE_ARCHIVE_NVIDIA50,
        )
        self.assertGreater(archives[0].size, 8_000_000_000)

    def test_extracts_nested_gpt_sovits_engine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source" / "package" / "GPT-SoVITS"
            source.mkdir(parents=True)
            (source / "api_v2.py").write_text("# api", encoding="utf-8")
            config = source / "GPT_SoVITS" / "configs"
            config.mkdir(parents=True)
            (config / "tts_infer.yaml").write_text(
                "device: cpu",
                encoding="utf-8",
            )
            archive = root / "engine.7z"
            subprocess.run(
                [
                    str(BUNDLED_7ZIP),
                    "a",
                    "-t7z",
                    str(archive),
                    "package",
                ],
                cwd=root / "source",
                check=True,
                capture_output=True,
            )

            destination = root / "installed" / "GPT-SoVITS"
            progress: list[tuple[int, int, str]] = []
            _extract_gpt_sovits_archive(
                archive,
                destination,
                lambda completed, total, current: progress.append(
                    (completed, total, current)
                ),
            )

            self.assertTrue((destination / "api_v2.py").is_file())
            self.assertTrue(
                (
                    destination
                    / "GPT_SoVITS"
                    / "configs"
                    / "tts_infer.yaml"
                ).is_file()
            )
            self.assertTrue(progress)
            self.assertEqual(progress[-1][0], progress[-1][1])

    def test_tts_download_uses_dedicated_reference_repository(self) -> None:
        files = _tts_files()
        references = [
            item
            for item in files
            if item.relative_path.startswith("reference_voices/")
        ]

        self.assertEqual(len(references), 12)
        self.assertTrue(
            all(TTS_REFERENCE_MODEL in item.url for item in references)
        )
        happy = next(
            item
            for item in references
            if item.relative_path == "reference_voices/高兴/ref.mp3"
        )
        self.assertEqual(happy.size, 105_028)
        self.assertEqual(
            happy.sha256,
            "aed4a6391ee7241a70556559588beb2b03171ab9dc1afca317d04dc5f98be83c",
        )

    def test_same_size_file_with_wrong_hash_is_not_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            target = destination / "reference_voices" / "高兴" / "asr.txt"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"old")
            item = RemoteFile(
                url="https://example.invalid/asr.txt",
                relative_path="reference_voices/高兴/asr.txt",
                size=3,
                sha256=hashlib.sha256(b"new").hexdigest(),
            )
            worker = AssetDownloadWorker(
                "test",
                "tts",
                "test/model",
                destination,
            )

            self.assertFalse(worker._target_is_complete(item))

    def test_streams_verifies_and_marks_download(self) -> None:
        payload = b"AIpet download progress" * 4_096
        with tempfile.TemporaryDirectory() as source_directory:
            source = Path(source_directory)
            (source / "model.bin").write_bytes(payload)
            handler = lambda *args: _QuietHandler(
                *args,
                directory=source_directory,
            )
            server = http.server.ThreadingHTTPServer(
                ("127.0.0.1", 0),
                handler,
            )
            thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
            )
            thread.start()
            try:
                with tempfile.TemporaryDirectory() as output_directory:
                    partial = (
                        Path(output_directory) / "model.bin.part"
                    )
                    partial.write_bytes(payload[:100])
                    item = RemoteFile(
                        url=(
                            f"http://127.0.0.1:{server.server_port}/model.bin"
                        ),
                        relative_path="model.bin",
                        size=len(payload),
                        sha256=hashlib.sha256(payload).hexdigest(),
                    )
                    worker = AssetDownloadWorker(
                        "test",
                        "whisper",
                        "test/model",
                        Path(output_directory),
                    )
                    completed: list[str] = []
                    failed: list[str] = []
                    worker.completed.connect(
                        lambda _job, path: completed.append(path)
                    )
                    worker.failed.connect(
                        lambda _job, message: failed.append(message)
                    )
                    with patch.object(
                        worker,
                        "_prepare_files",
                        return_value=[item],
                    ):
                        worker.run()

                    self.assertFalse(failed)
                    self.assertTrue(completed)
                    self.assertEqual(
                        (Path(output_directory) / "model.bin").read_bytes(),
                        payload,
                    )
                    self.assertTrue(
                        (
                            Path(output_directory)
                            / ".aipet-download.json"
                        ).is_file()
                    )
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
