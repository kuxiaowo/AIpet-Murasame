from __future__ import annotations

import hashlib
import http.server
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from classes.download_manager import (
    TTS_REFERENCE_MODEL,
    AssetDownloadWorker,
    RemoteFile,
    _tts_files,
)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass


class DownloadWorkerTests(unittest.TestCase):
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
