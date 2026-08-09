from __future__ import annotations

import hashlib
import http.server
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from aipet.core.download_manager import (
    BUNDLED_7ZIP,
    HUGGING_FACE_ENDPOINT,
    HUGGING_FACE_MIRROR_ENDPOINT,
    MODELSCOPE_ENDPOINT,
    TTS_ENGINE_ARCHIVE,
    TTS_ENGINE_ARCHIVE_NVIDIA50,
    TTS_REFERENCE_MODEL,
    TTS_WEIGHTS_MODEL,
    AssetDownloadWorker,
    DownloadManager,
    DownloadSnapshot,
    RemoteFile,
    _activate_extracted_engine,
    _extract_gpt_sovits_archive,
    _find_7zip,
    _modelscope_url,
    _sha256,
    _tts_files,
    _whisper_files,
    select_tts_engine_archive,
)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass


class DownloadWorkerTests(unittest.TestCase):
    @unittest.skipUnless(
        sys.platform == "win32",
        "Managed GPT-SoVITS engine downloads are a Windows-EXE capability",
    )
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
                    "aipet.core.download_manager.BUNDLED_7ZIP",
                    missing_bundled,
                ),
                patch(
                    "aipet.core.download_manager.shutil.which",
                    side_effect=lambda name: (
                        str(executable) if name == "7z" else None
                    ),
                ),
            ):
                self.assertEqual(_find_7zip(), executable.resolve())

    @unittest.skipUnless(
        sys.platform == "win32",
        "A bundled 7-Zip is only shipped inside the Windows build",
    )
    def test_prefers_bundled_7zip(self) -> None:
        self.assertTrue(BUNDLED_7ZIP.is_file())
        with patch(
            "aipet.core.download_manager.shutil.which",
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

    def test_manager_calculates_download_speed_from_recent_progress(
        self,
    ) -> None:
        manager = DownloadManager()
        manager._snapshots["test"] = DownloadSnapshot(
            status="checking",
            received=100,
            total=10_000,
        )
        with patch(
            "aipet.core.download_manager.time.monotonic",
            side_effect=[10.0, 11.0, 12.0],
        ):
            manager._on_progress("test", 100, 10_000, "model.bin")
            manager._on_progress("test", 1_124, 10_000, "model.bin")
            manager._on_progress("test", 3_172, 10_000, "model.bin")

        snapshot = manager.snapshot("test")
        self.assertEqual(snapshot.status, "downloading")
        self.assertEqual(snapshot.speed_bps, 1_536.0)

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

    @unittest.skipUnless(
        sys.platform == "win32",
        "Managed GPT-SoVITS engine archives are a Windows-EXE capability",
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

    @unittest.skipUnless(
        sys.platform == "win32",
        "Managed GPT-SoVITS engine archives are a Windows-EXE capability",
    )
    def test_tts_download_includes_selected_engine_archive(self) -> None:
        with patch(
            "aipet.core.download_manager.detect_nvidia_gpu_names",
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

    @unittest.skipUnless(
        sys.platform == "win32",
        "Managed GPT-SoVITS engine archives are a Windows-EXE capability",
    )
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
        weights = [
            item
            for item in files
            if not item.relative_path.startswith("reference_voices/")
        ]
        references = [
            item
            for item in files
            if item.relative_path.startswith("reference_voices/")
        ]

        self.assertEqual(len(weights), 2)
        self.assertTrue(
            all(
                item.url.startswith(
                    f"{MODELSCOPE_ENDPOINT}/{TTS_WEIGHTS_MODEL}/"
                )
                for item in weights
            )
        )
        self.assertEqual(len(references), 12)
        self.assertTrue(
            all(
                item.url.startswith(
                    f"{MODELSCOPE_ENDPOINT}/{TTS_REFERENCE_MODEL}/"
                )
                for item in references
            )
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
        self.assertEqual(
            happy.url,
            f"{MODELSCOPE_ENDPOINT}/{TTS_REFERENCE_MODEL}"
            "/resolve/master/reference_voices/"
            "%E9%AB%98%E5%85%B4/ref.mp3",
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

    def test_modelscope_url_quotes_unicode_file_paths(self) -> None:
        self.assertEqual(
            _modelscope_url(
                "owner/repository",
                "reference_voices/平静/ref.wav",
            ),
            f"{MODELSCOPE_ENDPOINT}/owner/repository/resolve/master/"
            "reference_voices/%E5%B9%B3%E9%9D%99/ref.wav",
        )

    def test_whisper_metadata_and_files_fall_back_to_hf_mirror(self) -> None:
        metadata = Mock()
        metadata.raise_for_status.return_value = None
        metadata.json.return_value = {
            "siblings": [
                {
                    "rfilename": "model.bin",
                    "size": 5,
                    "lfs": {"sha256": hashlib.sha256(b"model").hexdigest()},
                },
                {"rfilename": "config.json", "size": 2},
                {"rfilename": "unneeded.txt", "size": 99},
            ]
        }
        repository = "custom-owner/custom-whisper"
        with patch(
            "aipet.core.download_manager.requests.get",
            side_effect=[requests.Timeout("primary timeout"), metadata],
        ) as get:
            files = _whisper_files(repository)

        self.assertEqual(
            [call.args[0] for call in get.call_args_list],
            [
                f"{HUGGING_FACE_ENDPOINT}/api/models/{repository}",
                f"{HUGGING_FACE_MIRROR_ENDPOINT}/api/models/{repository}",
            ],
        )
        self.assertEqual(
            {item.relative_path for item in files},
            {"model.bin", "config.json"},
        )
        model = next(item for item in files if item.relative_path == "model.bin")
        self.assertEqual(
            model.url,
            f"{HUGGING_FACE_ENDPOINT}/{repository}/resolve/main/model.bin",
        )
        self.assertEqual(
            model.fallback_urls,
            (
                f"{HUGGING_FACE_MIRROR_ENDPOINT}/{repository}"
                "/resolve/main/model.bin",
            ),
        )

    def test_whisper_file_falls_back_and_resumes_on_mirror(self) -> None:
        payload = b"whisper mirror fallback"

        class Response:
            def __init__(self, status_code: int, body: bytes):
                self.status_code = status_code
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

            def raise_for_status(self) -> None:
                if self.status_code >= 400:
                    raise requests.HTTPError(str(self.status_code))

            def iter_content(self, chunk_size: int):
                del chunk_size
                yield self.body

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            (destination / "model.bin.part").write_bytes(payload[:8])
            item = RemoteFile(
                url="https://huggingface.co/test/model/resolve/main/model.bin",
                fallback_urls=(
                    "https://hf-mirror.com/test/model/resolve/main/model.bin",
                ),
                relative_path="model.bin",
                size=len(payload),
                sha256=hashlib.sha256(payload).hexdigest(),
            )
            calls: list[tuple[str, dict[str, str]]] = []

            def get(url: str, **kwargs):
                calls.append((url, kwargs["headers"]))
                if "huggingface.co" in url:
                    return Response(503, b"")
                return Response(206, payload[8:])

            worker = AssetDownloadWorker(
                "test",
                "whisper",
                "test/model",
                destination,
            )
            with patch(
                "aipet.core.download_manager.requests.get",
                side_effect=get,
            ):
                received = worker._download_file(item, 0, len(payload))

            self.assertEqual(received, len(payload))
            self.assertEqual((destination / "model.bin").read_bytes(), payload)
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][1]["Range"], "bytes=8-")
            self.assertEqual(calls[1][1]["Range"], "bytes=8-")

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
