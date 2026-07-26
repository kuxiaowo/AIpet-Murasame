from __future__ import annotations

import csv
from pathlib import Path

import cv2
import numpy as np

from tool.config import PROJECT_ROOT


PORTRAIT_TARGETS = {"ムラサメa", "ムラサメb"}
BASE_LAYER_RANGES = {
    "ムラサメa": slice(57, 65),
    "ムラサメb": slice(47, 51),
}


def _read_metadata(target: str) -> list[list[str]]:
    metadata_path = PROJECT_ROOT / "fgimages" / f"{target}.txt"
    with metadata_path.open(encoding="utf-16-le", newline="") as file:
        return list(csv.reader(file, delimiter="\t"))


def generate_fgimage(target: str, layer_ids: list[int]) -> np.ndarray:
    """Compose selected portrait layers into a BGRA image."""

    if target not in PORTRAIT_TARGETS:
        raise ValueError(f"Unknown portrait target: {target}")
    if not layer_ids:
        raise ValueError("At least one portrait layer is required")

    metadata = _read_metadata(target)
    base_rows = metadata[BASE_LAYER_RANGES[target]]
    base_positions = [
        (int(row[2]), int(row[3]), int(row[4]), int(row[5]))
        for row in base_rows
    ]
    if not base_positions:
        raise RuntimeError(f"No base metadata found for {target}")

    rows_by_id = {
        int(row[9]): row
        for row in metadata
        if len(row) > 9 and row[9].strip().isdigit()
    }
    missing = [layer_id for layer_id in layer_ids if layer_id not in rows_by_id]
    if missing:
        raise ValueError(f"Portrait layers do not exist: {missing}")

    origin_x = min(position[0] for position in base_positions)
    origin_y = min(position[1] for position in base_positions)
    layers: list[tuple[Path, int, int]] = []
    canvas_width = 0
    canvas_height = 0

    for layer_id in layer_ids:
        row = rows_by_id[layer_id]
        left, top, width, height = map(int, row[2:6])
        x = left - origin_x
        y = top - origin_y
        image_path = (
            PROJECT_ROOT / "fgimages" / f"{target}_{layer_id}.png"
        )
        if not image_path.exists():
            raise FileNotFoundError(f"Portrait layer is missing: {image_path}")
        layers.append((image_path, x, y))
        canvas_width = max(canvas_width, x + width)
        canvas_height = max(canvas_height, y + height)

    canvas = np.zeros((canvas_height, canvas_width, 4), dtype=np.uint8)
    for image_path, x, y in layers:
        image = cv2.imdecode(
            np.fromfile(str(image_path), dtype=np.uint8),
            cv2.IMREAD_UNCHANGED,
        )
        if image is None or image.ndim != 3 or image.shape[2] != 4:
            raise RuntimeError(f"Invalid portrait layer image: {image_path}")

        height, width = image.shape[:2]
        region = canvas[y : y + height, x : x + width]
        source_alpha = image[..., 3:4].astype(np.float32) / 255.0
        target_alpha = region[..., 3:4].astype(np.float32) / 255.0
        output_alpha = source_alpha + target_alpha * (1.0 - source_alpha)

        source_rgb = image[..., :3].astype(np.float32)
        target_rgb = region[..., :3].astype(np.float32)
        numerator = (
            source_rgb * source_alpha
            + target_rgb * target_alpha * (1.0 - source_alpha)
        )
        output_rgb = np.divide(
            numerator,
            output_alpha,
            out=np.zeros_like(numerator),
            where=output_alpha > 0,
        )
        region[..., :3] = np.clip(output_rgb, 0, 255).astype(np.uint8)
        region[..., 3:4] = np.clip(output_alpha * 255, 0, 255).astype(
            np.uint8
        )

    return canvas
