from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from geoscalex.geometry.analysis import GeometryValidationError, validate_geometry


@dataclass(frozen=True)
class NormalizedGeometry:
    geometry_type: str
    coordinates: list[list[float]]
    source_coordinates: list[list[float]]
    center: tuple[float, float]
    scale: float


def normalize_for_model(geometry: dict[str, Any]) -> NormalizedGeometry:
    analysis = validate_geometry(geometry)
    if analysis.geometry_type == "Polygon":
        if analysis.ring_count != 1:
            raise GeometryValidationError("Learned simplification only supports exterior rings")
        source = [list(point) for point in analysis.geometry["coordinates"][0][:-1]]
    else:
        source = [list(point) for point in analysis.geometry["coordinates"]]
    xs = [point[0] for point in source]
    ys = [point[1] for point in source]
    center = (sum(xs) / len(xs), sum(ys) / len(ys))
    scale = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)
    coordinates = [
        [round((point[0] - center[0]) / scale, 6), round((point[1] - center[1]) / scale, 6)]
        for point in source
    ]
    return NormalizedGeometry(analysis.geometry_type, coordinates, source, center, scale)


def apply_keep_move(
    normalized: NormalizedGeometry,
    kept_indices: list[int],
    offsets: list[tuple[float, float]],
    budget: int,
) -> tuple[dict[str, Any], dict[str, float]]:
    if len(kept_indices) != budget or len(offsets) != budget:
        raise GeometryValidationError("Proposal does not satisfy the exact vertex budget")
    if len(set(kept_indices)) != budget or kept_indices != sorted(kept_indices):
        raise GeometryValidationError("Retained indices must be distinct and source ordered")
    if (
        not kept_indices
        or kept_indices[0] < 0
        or kept_indices[-1] >= len(normalized.source_coordinates)
    ):
        raise GeometryValidationError("Retained index is outside the source geometry")
    if normalized.geometry_type == "LineString":
        if kept_indices[0] != 0 or kept_indices[-1] != len(normalized.source_coordinates) - 1:
            raise GeometryValidationError("Line endpoints must be retained")
        if offsets[0] != (0.0, 0.0) or offsets[-1] != (0.0, 0.0):
            raise GeometryValidationError("Line endpoints must not move")

    moved: list[list[float]] = []
    magnitudes: list[float] = []
    for index, offset in zip(kept_indices, offsets, strict=True):
        if not all(math.isfinite(value) and abs(value) <= 0.05 for value in offset):
            raise GeometryValidationError("Coordinate offset exceeds the configured limit")
        source = normalized.source_coordinates[index]
        moved.append(
            [source[0] + offset[0] * normalized.scale, source[1] + offset[1] * normalized.scale]
        )
        magnitudes.append(math.hypot(*offset) * normalized.scale)
    if normalized.geometry_type == "Polygon":
        geometry: dict[str, Any] = {"type": "Polygon", "coordinates": [[*moved, moved[0]]]}
    else:
        geometry = {"type": "LineString", "coordinates": moved}
    result = validate_geometry(geometry).geometry
    return result, {
        "moved_vertex_count": float(sum(magnitude > 0 for magnitude in magnitudes)),
        "maximum_displacement": max(magnitudes, default=0.0),
        "mean_displacement": sum(magnitudes) / len(magnitudes) if magnitudes else 0.0,
    }
