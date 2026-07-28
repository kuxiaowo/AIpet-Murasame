from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable
from urllib.parse import quote

import requests
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from tool.config import PROJECT_ROOT
from tool.runtime_logging import get_logger
from tool.whisper_models import model_repository


logger = get_logger("download")


TTS_JOB_ID = "tts:murasame"
TTS_MODEL_NAME = "Murasame_SoVITS"
TTS_REFERENCE_MODEL = "kuxiaowo/Murasame-tts-reference-voice"
TTS_ENGINE_MODEL = "FlowerCry/gpt-sovits-7z-pacakges"
TTS_ENGINE_ARCHIVE = "GPT-SoVITS-v2pro-20250604.7z"
TTS_ENGINE_ARCHIVE_NVIDIA50 = (
    "GPT-SoVITS-v2pro-20250604-nvidia50.7z"
)
TTS_ENGINE_ARCHIVES = {
    TTS_ENGINE_ARCHIVE: (
        8_185_086_602,
        "bd60d0796553ff05d8568136e199c13e0dc22ebe2ed24273134e34ed6f215cd6",
    ),
    TTS_ENGINE_ARCHIVE_NVIDIA50: (
        8_835_144_925,
        "97b4edcd451c42357db7e26e6c1c877ca5d85144fe97beaff6d7005d35bee008",
    ),
}
BUNDLED_7ZIP = (
    PROJECT_ROOT
    / "packaging"
    / "vendor"
    / "7zip"
    / "7zr.exe"
)


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
    prepared = pyqtSignal(str, object)
    checking = pyqtSignal(str, object, object, str)
    progress = pyqtSignal(str, object, object, str)
    extracting = pyqtSignal(str, object, object, str)
    installing = pyqtSignal(str, str, object, object, str)
    completed = pyqtSignal(str, str)
    failed = pyqtSignal(str, str)

    def __init__(
        self,
        job_id: str,
        kind: str,
        identifier: str,
        destination: Path,
        include_tts_engine: bool = False,
        *,
        tts_engine_destination: Path | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.job_id = job_id
        self.kind = kind
        self.identifier = identifier
        self.destination = destination
        self.include_tts_engine = include_tts_engine
        self.tts_engine_destination = tts_engine_destination
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
            hash_candidates = [
                item
                for item in files
                if self._target_needs_hash(item)
            ]
            check_total = sum(item.size for item in hash_candidates)
            checked_before = 0
            complete_paths: set[str] = set()
            self.checking.emit(self.job_id, 0, check_total, "")
            for item in files:
                if self._cancelled.is_set():
                    return
                is_hash_candidate = item in hash_candidates
                if self._target_is_complete(
                    item,
                    (
                        lambda completed, current=item: self.checking.emit(
                            self.job_id,
                            checked_before + completed,
                            check_total,
                            current.relative_path,
                        )
                    )
                    if is_hash_candidate
                    else None,
                ):
                    complete_paths.add(item.relative_path)
                if is_hash_candidate:
                    checked_before += item.size
            received = sum(
                item.size
                for item in files
                if item.relative_path in complete_paths
            )
            self.progress.emit(self.job_id, received, total, "")

            for item in files:
                if self._cancelled.is_set():
                    return
                if item.relative_path in complete_paths:
                    continue
                received = self._download_file(item, received, total)

            if self.kind == "tts" and self.include_tts_engine:
                self._install_tts_engine(files, total)

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
            return _tts_files(include_engine=self.include_tts_engine)
        if self.kind == "whisper":
            return _whisper_files(self.identifier)
        raise ValueError(f"Unsupported download kind: {self.kind}")

    def _target_needs_hash(self, item: RemoteFile) -> bool:
        target = self.destination / item.relative_path
        try:
            return (
                bool(item.sha256)
                and target.is_file()
                and target.stat().st_size == item.size
            )
        except OSError:
            return False

    def _target_is_complete(
        self,
        item: RemoteFile,
        hash_progress: Callable[[int], None] | None = None,
    ) -> bool:
        target = self.destination / item.relative_path
        try:
            if not target.is_file() or target.stat().st_size != item.size:
                return False
            return (
                not item.sha256
                or _sha256(target, hash_progress) == item.sha256.lower()
            )
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
            if item.sha256 and self._verified_sha256(
                partial,
                item,
            ) != item.sha256.lower():
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
            timeout=(15, 60 if item.size > 1_000_000_000 else 15),
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
        if item.sha256 and self._verified_sha256(
            partial,
            item,
        ) != item.sha256.lower():
            partial.unlink(missing_ok=True)
            raise RuntimeError(
                f"{item.relative_path}: SHA-256 verification failed"
            )
        os.replace(partial, target)
        return completed_before + item.size

    def _verified_sha256(
        self,
        path: Path,
        item: RemoteFile,
    ) -> str:
        return _sha256(
            path,
            lambda completed: self.checking.emit(
                self.job_id,
                completed,
                item.size,
                item.relative_path,
            ),
        )

    def _install_tts_engine(
        self,
        files: list[RemoteFile],
        total: int,
    ) -> None:
        archive_item = next(
            (
                item
                for item in files
                if item.relative_path.startswith(".downloads/")
                and item.relative_path.endswith(".7z")
            ),
            None,
        )
        if archive_item is None:
            raise RuntimeError("GPT-SoVITS engine archive was not prepared")
        if self.tts_engine_destination is None:
            raise RuntimeError("GPT-SoVITS download directory was not provided")
        archive = self.destination / archive_item.relative_path
        _extract_gpt_sovits_archive(
            archive,
            self.tts_engine_destination,
            progress_callback=lambda completed, count, current: (
                self.extracting.emit(
                    self.job_id,
                    completed,
                    count,
                    current,
                )
            ),
            install_callback=lambda stage, completed, count, current: (
                self.installing.emit(
                    self.job_id,
                    stage,
                    completed,
                    count,
                    current,
                )
            ),
        )
        archive.unlink(missing_ok=True)


class DownloadManager(QObject):
    changed = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workers: dict[str, AssetDownloadWorker] = {}
        self._snapshots: dict[str, DownloadSnapshot] = {}

    def snapshot(self, job_id: str) -> DownloadSnapshot:
        return self._snapshots.get(job_id, DownloadSnapshot())

    def start_whisper(
        self,
        model_name: str,
        destination: Path,
    ) -> str:
        repository = model_repository(model_name)
        job_id = whisper_job_id(repository)
        self._start(job_id, "whisper", repository, destination)
        return job_id

    def start_tts(
        self,
        model_destination: Path,
        *,
        include_engine: bool = False,
        engine_destination: Path | None = None,
    ) -> str:
        if include_engine and engine_destination is None:
            raise ValueError(
                "GPT-SoVITS download directory is required"
            )
        self._start(
            TTS_JOB_ID,
            "tts",
            TTS_MODEL_NAME,
            model_destination,
            include_tts_engine=include_engine,
            tts_engine_destination=engine_destination,
        )
        return TTS_JOB_ID

    def _start(
        self,
        job_id: str,
        kind: str,
        identifier: str,
        destination: Path,
        include_tts_engine: bool = False,
        tts_engine_destination: Path | None = None,
    ) -> None:
        existing = self._workers.get(job_id)
        if existing is not None and existing.isRunning():
            return

        worker = AssetDownloadWorker(
            job_id,
            kind,
            identifier,
            destination,
            include_tts_engine,
            tts_engine_destination=tts_engine_destination,
            parent=self,
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
        worker.checking.connect(self._on_checking)
        worker.progress.connect(self._on_progress)
        worker.extracting.connect(self._on_extracting)
        worker.installing.connect(self._on_installing)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda: self._finish_worker(job_id, worker))
        worker.start()

    def _on_prepared(self, job_id: str, total: int) -> None:
        current = self.snapshot(job_id)
        self._publish(
            job_id,
            DownloadSnapshot(
                status="checking",
                total=total,
                destination=current.destination,
            ),
        )

    def _on_checking(
        self,
        job_id: str,
        completed: int,
        total: int,
        current_file: str,
    ) -> None:
        current = self.snapshot(job_id)
        self._publish(
            job_id,
            DownloadSnapshot(
                status="checking",
                received=completed,
                total=total,
                current_file=current_file,
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

    def _on_extracting(
        self,
        job_id: str,
        completed: int,
        total: int,
        current_file: str,
    ) -> None:
        current = self.snapshot(job_id)
        self._publish(
            job_id,
            DownloadSnapshot(
                status="extracting",
                received=completed,
                total=total,
                current_file=current_file,
                destination=current.destination,
            ),
        )

    def _on_installing(
        self,
        job_id: str,
        stage: str,
        completed: int,
        total: int,
        current_file: str,
    ) -> None:
        current = self.snapshot(job_id)
        self._publish(
            job_id,
            DownloadSnapshot(
                status=stage,
                received=completed,
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
        previous = self._snapshots.get(job_id)
        self._snapshots[job_id] = snapshot
        if previous is None or previous.status != snapshot.status:
            if snapshot.status == "failed":
                logger.error(
                    "下载任务失败 | %s | 目标=%s | %s",
                    job_id,
                    snapshot.destination or "-",
                    snapshot.message,
                )
            else:
                logger.info(
                    "下载任务状态 | %s | %s | 目标=%s",
                    job_id,
                    snapshot.status,
                    snapshot.destination or "-",
                )
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


def _tts_files(*, include_engine: bool = False) -> list[RemoteFile]:
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
    if include_engine:
        archive_name = select_tts_engine_archive()
        size, sha256 = TTS_ENGINE_ARCHIVES[archive_name]
        engine_base = (
            "https://www.modelscope.cn/models/"
            f"{TTS_ENGINE_MODEL}/resolve/master"
        )
        files.append(
            RemoteFile(
                url=f"{engine_base}/{archive_name}",
                relative_path=f".downloads/{archive_name}",
                size=size,
                sha256=sha256,
            )
        )
    return files


def select_tts_engine_archive(gpu_names: list[str] | None = None) -> str:
    names = gpu_names if gpu_names is not None else detect_nvidia_gpu_names()
    if any(
        re.search(
            r"\bGeForce\s+RTX\s*50\d{2}\b",
            name,
            flags=re.IGNORECASE,
        )
        for name in names
    ):
        return TTS_ENGINE_ARCHIVE_NVIDIA50
    return TTS_ENGINE_ARCHIVE


def detect_nvidia_gpu_names() -> list[str]:
    command = shutil.which("nvidia-smi")
    if command is None:
        return []
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(
            [
                command,
                "--query-gpu=name",
                "--format=csv,noheader",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


def _extract_gpt_sovits_archive(
    archive: Path,
    destination: Path,
    progress_callback: Callable[[int, int, str], None] | None = None,
    install_callback: (
        Callable[[str, int, int, str], None] | None
    ) = None,
) -> None:
    staging = destination.parent / (
        f".{destination.name}-extract-{uuid.uuid4().hex}"
    )
    staging.mkdir(parents=True, exist_ok=False)
    try:
        seven_zip = _find_7zip()
        if seven_zip is not None:
            _extract_with_7zip(
                seven_zip,
                archive,
                staging,
                progress_callback,
            )
        elif not _extract_with_bsdtar(
            archive,
            staging,
            progress_callback,
        ):
            raise RuntimeError(
                "7-Zip or Windows tar/bsdtar is required to extract "
                "this BCJ2-compressed GPT-SoVITS package"
            )

        if install_callback is not None:
            install_callback("installing", 0, 3, "locating api_v2.py")
        api_candidates = sorted(
            staging.rglob("api_v2.py"),
            key=lambda item: len(item.parts),
        )
        if not api_candidates:
            raise RuntimeError(
                "Extracted package does not contain api_v2.py"
            )
        source = api_candidates[0].parent
        _activate_extracted_engine(
            source,
            destination,
            install_callback,
        )
    finally:
        if install_callback is not None and staging.exists():
            install_callback(
                "cleaning",
                0,
                0,
                "temporary extraction directory",
            )
        shutil.rmtree(staging, ignore_errors=True)


def _find_7zip() -> Path | None:
    if os.name == "nt" and BUNDLED_7ZIP.is_file():
        return BUNDLED_7ZIP.resolve()

    candidates = [
        shutil.which(name)
        for name in ("7z", "7zz", "7za", "7zr")
    ]
    if os.name == "nt":
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.getenv(variable, "").strip()
            if root:
                candidates.append(str(Path(root) / "7-Zip" / "7z.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    return None


def _extract_with_7zip(
    command: Path,
    archive: Path,
    destination: Path,
    progress_callback: Callable[[int, int, str], None] | None,
) -> None:
    startupinfo, creationflags = _hidden_process_options()
    listing = subprocess.run(
        [str(command), "l", "-slt", str(archive)],
        check=True,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=120,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    after_separator = False
    names: list[str] = []
    for line in listing.stdout.splitlines():
        if line.startswith("----------"):
            after_separator = True
            continue
        if after_separator and line.startswith("Path = "):
            names.append(line[7:].strip())
    _validate_archive_names(names)
    if progress_callback is not None:
        progress_callback(0, 100, archive.name)

    process = subprocess.Popen(
        [
            str(command),
            "x",
            "-y",
            "-mmt=on",
            "-bsp1",
            "-bb0",
            f"-o{destination}",
            str(archive),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    recent_output: deque[str] = deque(maxlen=20)
    buffer = ""
    last_percent = -1
    assert process.stdout is not None
    while True:
        character = process.stdout.read(1)
        if not character:
            break
        if character not in {"\r", "\n"}:
            buffer += character
            continue
        current = buffer.strip()
        buffer = ""
        if not current:
            continue
        recent_output.append(current)
        match = re.search(r"(\d+)%", current)
        if match:
            percent = min(100, int(match.group(1)))
            if percent != last_percent and progress_callback is not None:
                progress_callback(percent, 100, archive.name)
            last_percent = percent
    process.stdout.close()
    return_code = process.wait()
    if return_code != 0:
        detail = "\n".join(recent_output)
        raise RuntimeError(
            f"7-Zip extraction failed ({return_code}): {detail}"
        )
    if progress_callback is not None:
        progress_callback(100, 100, archive.name)


def _activate_extracted_engine(
    source: Path,
    destination: Path,
    install_callback: (
        Callable[[str, int, int, str], None] | None
    ),
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup: Path | None = None
    if destination.exists():
        backup = destination.parent / (
            f".{destination.name}-backup-{uuid.uuid4().hex}"
        )
        if install_callback is not None:
            install_callback(
                "installing",
                1,
                3,
                "preserving previous installation",
            )
        os.replace(destination, backup)
    try:
        if install_callback is not None:
            install_callback(
                "installing",
                2,
                3,
                "activating GPT-SoVITS",
            )
        os.replace(source, destination)
        if not (destination / "api_v2.py").is_file():
            raise RuntimeError("GPT-SoVITS engine installation failed")
        if install_callback is not None:
            install_callback(
                "installing",
                3,
                3,
                "GPT-SoVITS installed",
            )
    except Exception:
        if destination.exists():
            failed = destination.parent / (
                f".{destination.name}-failed-{uuid.uuid4().hex}"
            )
            os.replace(destination, failed)
            shutil.rmtree(failed, ignore_errors=True)
        if backup is not None and backup.exists():
            os.replace(backup, destination)
        raise
    if backup is not None and backup.exists():
        if install_callback is not None:
            install_callback(
                "cleaning",
                0,
                0,
                "previous installation",
            )
        shutil.rmtree(backup, ignore_errors=True)


def _extract_with_bsdtar(
    archive: Path,
    destination: Path,
    progress_callback: Callable[[int, int, str], None] | None,
) -> bool:
    command = shutil.which("tar")
    if command is None:
        return False
    startupinfo, creationflags = _hidden_process_options()
    try:
        listing = subprocess.run(
            [command, "-tf", str(archive)],
            check=True,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=120,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Timed out while reading the GPT-SoVITS archive"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(
            f"bsdtar cannot read the GPT-SoVITS archive: {detail}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Failed to start Windows tar/bsdtar: {exc}"
        ) from exc

    names = [
        line.strip()
        for line in listing.stdout.splitlines()
        if line.strip()
    ]
    _validate_archive_names(names)
    total = max(1, len(names))
    if progress_callback is not None:
        progress_callback(0, total, archive.name)

    process = subprocess.Popen(
        [
            command,
            "-xvf",
            str(archive),
            "-C",
            str(destination),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    recent_output: deque[str] = deque(maxlen=20)
    completed = 0
    assert process.stdout is not None
    for line in process.stdout:
        current = line.strip()
        if not current:
            continue
        recent_output.append(current)
        completed += 1
        if progress_callback is not None:
            progress_callback(
                min(completed, total),
                total,
                current,
            )
    process.stdout.close()
    return_code = process.wait()
    if return_code != 0:
        detail = "\n".join(recent_output)
        raise RuntimeError(
            f"bsdtar extraction failed ({return_code}): {detail}"
        )
    if progress_callback is not None:
        progress_callback(total, total, archive.name)
    return True


def _validate_archive_names(names: list[str]) -> None:
    if not names:
        raise RuntimeError("GPT-SoVITS archive is empty")
    for name in names:
        normalized = PurePosixPath(name.replace("\\", "/"))
        if (
            normalized.is_absolute()
            or ".." in normalized.parts
            or (
                normalized.parts
                and ":" in normalized.parts[0]
            )
        ):
            raise RuntimeError(
                f"Unsafe path in GPT-SoVITS archive: {name}"
            )


def _hidden_process_options() -> tuple[object | None, int]:
    if os.name != "nt":
        return None, 0
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startupinfo, subprocess.CREATE_NO_WINDOW


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


def _sha256(
    path: Path,
    progress_callback: Callable[[int], None] | None = None,
) -> str:
    digest = hashlib.sha256()
    completed = 0
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
            completed += len(chunk)
            if progress_callback is not None:
                progress_callback(completed)
    return digest.hexdigest()
