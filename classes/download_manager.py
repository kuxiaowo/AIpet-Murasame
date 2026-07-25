from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import requests
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from tool.tts_assets import managed_tts_model_dir
from tool.whisper_models import managed_whisper_dir, model_repository


TTS_JOB_ID = "tts:murasame"
TTS_MODEL_NAME = "Murasame_SoVITS"
TTS_MODEL_PAGE = "https://www.modelscope.cn/models/LemonQu/Murasame_SoVITS"
TTS_REFERENCE_MODEL = "kuxiaowo/Murasame-tts-reference-voice"


@dataclass(frozen=True)
class RemoteFile:
    url: str
    relative_path: str
    size: int
    sha256: str = ""


@dataclass(frozen=True)
class DownloadSnapshot:
    status: str = "idle"
    received: int = 0
    total: int = 0
    current_file: str = ""
    message: str = ""
    destination: str = ""


class AssetDownloadWorker(QThread):
    prepared = pyqtSignal(str, int)
    progress = pyqtSignal(str, int, int, str)
    completed = pyqtSignal(str, str)
    failed = pyqtSignal(str, str)

    def __init__(
        self,
        job_id: str,
        kind: str,
        identifier: str,
        destination: Path,
        parent=None,
    ):
        super().__init__(parent)
        self.job_id = job_id
        self.kind = kind
        self.identifier = identifier
        self.destination = destination
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()
        self.requestInterruption()

    def run(self) -> None:
        try:
            files = self._prepare_files()
            total = sum(item.size for item in files)
            self.prepared.emit(self.job_id, total)
            self.destination.mkdir(parents=True, exist_ok=True)
            received = sum(
                item.size
                for item in files
                if self._target_is_complete(item)
            )
            self.progress.emit(self.job_id, received, total, "")

            for item in files:
                if self._cancelled.is_set():
                    return
                if self._target_is_complete(item):
                    continue
                received = self._download_file(item, received, total)

            marker = self.destination / ".aipet-download.json"
            marker.write_text(
                json.dumps(
                    {
                        "kind": self.kind,
                        "identifier": self.identifier,
                        "files": [
                            {
                                "path": item.relative_path,
                                "size": item.size,
                                "sha256": item.sha256,
                            }
                            for item in files
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            self.completed.emit(self.job_id, str(self.destination.resolve()))
        except Exception as exc:
            if not self._cancelled.is_set():
                self.failed.emit(self.job_id, str(exc))

    def _prepare_files(self) -> list[RemoteFile]:
        if self.kind == "tts":
            return _tts_files()
        if self.kind == "whisper":
            return _whisper_files(self.identifier)
        raise ValueError(f"Unsupported download kind: {self.kind}")

    def _target_is_complete(self, item: RemoteFile) -> bool:
        target = self.destination / item.relative_path
        try:
            if not target.is_file() or target.stat().st_size != item.size:
                return False
            return not item.sha256 or _sha256(target) == item.sha256.lower()
        except OSError:
            return False

    def _download_file(
        self,
        item: RemoteFile,
        completed_before: int,
        total: int,
    ) -> int:
        target = self.destination / item.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        partial_size = partial.stat().st_size if partial.exists() else 0
        if partial_size > item.size:
            partial.unlink()
            partial_size = 0
        if partial_size == item.size:
            if item.sha256 and _sha256(partial) != item.sha256.lower():
                partial.unlink()
                partial_size = 0
            else:
                os.replace(partial, target)
                return completed_before + item.size

        headers = {"Accept-Encoding": "identity"}
        if partial_size:
            headers["Range"] = f"bytes={partial_size}-"
        with requests.get(
            item.url,
            headers=headers,
            stream=True,
            timeout=(15, 15),
        ) as response:
            if partial_size and response.status_code != 206:
                partial_size = 0
            response.raise_for_status()
            mode = "ab" if partial_size else "wb"
            downloaded = partial_size
            with partial.open(mode) as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if self._cancelled.is_set():
                        return completed_before + downloaded
                    if not chunk:
                        continue
                    output.write(chunk)
                    downloaded += len(chunk)
                    self.progress.emit(
                        self.job_id,
                        completed_before + downloaded,
                        total,
                        item.relative_path,
                    )

        if downloaded != item.size:
            raise RuntimeError(
                f"{item.relative_path}: expected {item.size} bytes, "
                f"received {downloaded}"
            )
        if item.sha256 and _sha256(partial) != item.sha256.lower():
            partial.unlink(missing_ok=True)
            raise RuntimeError(
                f"{item.relative_path}: SHA-256 verification failed"
            )
        os.replace(partial, target)
        return completed_before + item.size


class DownloadManager(QObject):
    changed = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: dict[str, AssetDownloadWorker] = {}
        self._snapshots: dict[str, DownloadSnapshot] = {}

    def snapshot(self, job_id: str) -> DownloadSnapshot:
        return self._snapshots.get(job_id, DownloadSnapshot())

    def start_whisper(self, model_name: str) -> str:
        repository = model_repository(model_name)
        job_id = whisper_job_id(repository)
        destination = managed_whisper_dir(repository)
        self._start(job_id, "whisper", repository, destination)
        return job_id

    def start_tts(self) -> str:
        self._start(
            TTS_JOB_ID,
            "tts",
            TTS_MODEL_NAME,
            managed_tts_model_dir(),
        )
        return TTS_JOB_ID

    def _start(
        self,
        job_id: str,
        kind: str,
        identifier: str,
        destination: Path,
    ) -> None:
        existing = self._workers.get(job_id)
        if existing is not None and existing.isRunning():
            return

        worker = AssetDownloadWorker(
            job_id,
            kind,
            identifier,
            destination,
            self,
        )
        self._workers[job_id] = worker
        self._publish(
            job_id,
            DownloadSnapshot(
                status="preparing",
                destination=str(destination),
            ),
        )
        worker.prepared.connect(self._on_prepared)
        worker.progress.connect(self._on_progress)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda: self._finish_worker(job_id, worker))
        worker.start()

    def _on_prepared(self, job_id: str, total: int) -> None:
        current = self.snapshot(job_id)
        self._publish(
            job_id,
            DownloadSnapshot(
                status="downloading",
                total=total,
                destination=current.destination,
            ),
        )

    def _on_progress(
        self,
        job_id: str,
        received: int,
        total: int,
        current_file: str,
    ) -> None:
        current = self.snapshot(job_id)
        self._publish(
            job_id,
            DownloadSnapshot(
                status="downloading",
                received=received,
                total=total,
                current_file=current_file,
                destination=current.destination,
            ),
        )

    def _on_completed(self, job_id: str, destination: str) -> None:
        current = self.snapshot(job_id)
        self._publish(
            job_id,
            DownloadSnapshot(
                status="completed",
                received=current.total,
                total=current.total,
                destination=destination,
            ),
        )

    def _on_failed(self, job_id: str, message: str) -> None:
        current = self.snapshot(job_id)
        self._publish(
            job_id,
            DownloadSnapshot(
                status="failed",
                received=current.received,
                total=current.total,
                current_file=current.current_file,
                message=message,
                destination=current.destination,
            ),
        )

    def _finish_worker(
        self,
        job_id: str,
        worker: AssetDownloadWorker,
    ) -> None:
        if self._workers.get(job_id) is worker:
            self._workers.pop(job_id, None)
        worker.deleteLater()

    def _publish(self, job_id: str, snapshot: DownloadSnapshot) -> None:
        self._snapshots[job_id] = snapshot
        self.changed.emit(job_id, snapshot)

    def shutdown(self) -> None:
        workers = list(self._workers.values())
        for worker in workers:
            worker.cancel()
        for worker in workers:
            if not worker.wait(17_000):
                worker.terminate()
                worker.wait(2_000)


def whisper_job_id(repository: str) -> str:
    return f"whisper:{repository}"


def _tts_files() -> list[RemoteFile]:
    weights_base = (
        "https://www.modelscope.cn/models/"
        "LemonQu/Murasame_SoVITS/resolve/master"
    )
    files = [
        RemoteFile(
            url=f"{weights_base}/murasame-gpt.ckpt",
            relative_path="murasame-gpt.ckpt",
            size=155_312_594,
            sha256=(
                "a0d6df8a0acda9efddbe0ce47e4317f2"
                "991cc9a46233cb8ab8d86744c568e85d"
            ),
        ),
        RemoteFile(
            url=f"{weights_base}/murasame-sovits.pth",
            relative_path="murasame-sovits.pth",
            size=75_550_062,
            sha256=(
                "2518d5ddb54ada45dad70a3ed3c27c70"
                "d2f9655e1d0dad5c8e81af2d7f3972c6"
            ),
        ),
    ]
    references_base = (
        "https://www.modelscope.cn/models/"
        f"{TTS_REFERENCE_MODEL}/resolve/master/reference_voices"
    )
    reference_files = (
        (
            "害羞/asr.txt",
            63,
            "213e5c69e9b86b5fb8796bb9b6305a89d4e447ee09e22bb25b051dd9b0373297",
        ),
        (
            "害羞/ref.mp3",
            41_901,
            "912f4002f42cb8c5e8e7cc7c901d44240bfcd3786a2f83129dde291350ceabfa",
        ),
        (
            "平静/asr.txt",
            43,
            "02c706057d76c5857273fc262229e4402d56f61625cfbb6ec21c911e7666cb36",
        ),
        (
            "平静/ref.wav",
            247_860,
            "5eb865365b4da7585c8971f19e1ca0fae4e5becf980223f5865bf0622751c31c",
        ),
        (
            "惊讶/asr.txt",
            48,
            "5c9a0e07414de068bff7c24978a83d71ee2bc0bc27e1f275efdac744dc14156a",
        ),
        (
            "惊讶/ref.mp3",
            24_621,
            "9bac5533e6c9412f69055716f6685cf9f9462c520785a55f72382ebc97ef7529",
        ),
        (
            "生气/asr.txt",
            60,
            "ca9b26c890b6eb2a0901fca50a733cafc6170a9c6fbaa673a24284c69a7ae8d6",
        ),
        (
            "生气/ref.mp3",
            28_269,
            "cb1054bdcf0c4ebd08e62f9a23a31cb25bdff7efee37493b6f54f17b59567e5d",
        ),
        (
            "着急/asr.txt",
            138,
            "4fd49ae64e6cfba94449bc7124d31d63a012d3e60277258324874b23672807d4",
        ),
        (
            "着急/ref.mp3",
            50_349,
            "e1be1035c99a19b7c8946f42d729f529829bb41a20f6dc4373bf0facd26ec407",
        ),
        (
            "高兴/asr.txt",
            51,
            "df578775ea648be05d863f9d0fd420ab27ad36bbfbdd123166c0de12d7954cbe",
        ),
        (
            "高兴/ref.mp3",
            105_028,
            "aed4a6391ee7241a70556559588beb2b03171ab9dc1afca317d04dc5f98be83c",
        ),
    )
    files.extend(
        RemoteFile(
            url=f"{references_base}/{quote(relative_path, safe='/')}",
            relative_path=f"reference_voices/{relative_path}",
            size=size,
            sha256=sha256,
        )
        for relative_path, size, sha256 in reference_files
    )
    return files


def _whisper_files(repository: str) -> list[RemoteFile]:
    response = requests.get(
        f"https://huggingface.co/api/models/{repository}",
        params={"blobs": "true"},
        timeout=(15, 45),
    )
    response.raise_for_status()
    payload = response.json()
    patterns = (
        "config.json",
        "preprocessor_config.json",
        "model.bin",
        "tokenizer.json",
        "vocabulary.*",
    )
    files: list[RemoteFile] = []
    for sibling in payload.get("siblings", []):
        name = str(sibling.get("rfilename", ""))
        if not name or not any(fnmatch.fnmatch(name, item) for item in patterns):
            continue
        size = int(sibling.get("size") or sibling.get("lfs", {}).get("size") or 0)
        if size <= 0:
            raise RuntimeError(f"Hugging Face did not report a size for {name}")
        sha256 = str(sibling.get("lfs", {}).get("sha256", ""))
        files.append(
            RemoteFile(
                url=(
                    f"https://huggingface.co/{repository}/resolve/main/"
                    f"{quote(name)}"
                ),
                relative_path=name,
                size=size,
                sha256=sha256,
            )
        )
    if not files or not any(item.relative_path == "model.bin" for item in files):
        raise RuntimeError(f"No faster-whisper model files found for {repository}")
    return files


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
