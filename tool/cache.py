from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from tool.config import get_cache_dir


CACHE_DATA_DIRECTORIES = ("screens", "voices", "recordings")


@dataclass(frozen=True)
class CacheClearResult:
    removed_files: int
    removed_bytes: int
    failed_paths: tuple[Path, ...] = ()


def clear_runtime_cache(cache_dir: Path | None = None) -> CacheClearResult:
    """Delete disposable runtime data while preserving logs and user data."""

    root = cache_dir or get_cache_dir()
    removed_files = 0
    removed_bytes = 0
    failed_paths: list[Path] = []

    for directory_name in CACHE_DATA_DIRECTORIES:
        directory = root / directory_name
        if not directory.exists():
            continue
        if directory.is_symlink() or not directory.is_dir():
            failed_paths.append(directory)
            continue

        for current_root, directory_names, file_names in os.walk(
            directory,
            topdown=False,
            followlinks=False,
        ):
            current = Path(current_root)
            for file_name in file_names:
                path = current / file_name
                try:
                    size = path.lstat().st_size
                    path.unlink()
                except FileNotFoundError:
                    continue
                except OSError:
                    failed_paths.append(path)
                else:
                    removed_files += 1
                    removed_bytes += size

            for child_name in directory_names:
                path = current / child_name
                try:
                    if path.is_symlink():
                        path.unlink()
                        removed_files += 1
                    else:
                        path.rmdir()
                except FileNotFoundError:
                    continue
                except OSError:
                    # A directory containing an in-use file is expected to
                    # remain. The file failure already carries the useful
                    # information, so do not report the directory twice.
                    if not any(
                        failed == path or path in failed.parents
                        for failed in failed_paths
                    ):
                        failed_paths.append(path)

    return CacheClearResult(
        removed_files=removed_files,
        removed_bytes=removed_bytes,
        failed_paths=tuple(failed_paths),
    )
