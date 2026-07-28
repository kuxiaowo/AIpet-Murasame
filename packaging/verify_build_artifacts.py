from __future__ import annotations

import argparse
import hashlib
import subprocess
import tempfile
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader


EXTRACTOR_ENTRY = r"packaging\vendor\7zip\7zr.exe"
NOTICE_ENTRY = r"packaging\vendor\7zip\README.md"
EXTRACTOR_SHA256 = (
    "56b8cc9f4971cef253644fafe54063ed7fdca551d4dee0f8c6baa81b855acd72"
)


def verify_artifact(path: Path) -> None:
    archive = CArchiveReader(str(path))
    extractor = archive.extract(EXTRACTOR_ENTRY)
    archive.extract(NOTICE_ENTRY)

    actual_hash = hashlib.sha256(extractor).hexdigest()
    if actual_hash != EXTRACTOR_SHA256:
        raise RuntimeError(
            f"{path.name}: embedded 7zr.exe SHA-256 mismatch: "
            f"{actual_hash}"
        )

    with tempfile.TemporaryDirectory(prefix="aipet-7zr-check-") as directory:
        executable = Path(directory) / "7zr.exe"
        executable.write_bytes(extractor)
        result = subprocess.run(
            [str(executable)],
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=30,
        )
        output = f"{result.stdout}\n{result.stderr}"
        if result.returncode != 0 or "7-Zip" not in output:
            raise RuntimeError(
                f"{path.name}: embedded 7zr.exe did not execute correctly"
            )

    print(
        f"Verified {path.name}: embedded 7zr.exe "
        f"SHA-256 {actual_hash}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify bundled runtime assets in AIpet executables."
    )
    parser.add_argument("artifacts", nargs="+", type=Path)
    args = parser.parse_args()
    for artifact in args.artifacts:
        verify_artifact(artifact.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
