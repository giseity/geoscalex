from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from shapely import frechet_distance, hausdorff_distance
from shapely.geometry import LineString, Polygon, mapping, shape
from shapely.validation import explain_validity

SUPPORTED_TYPES = {"LineString", "Polygon"}


class GeometryValidationError(ValueError):
    pass


@dataclass(frozen=True)
class GeometryAnalysis:
    geometry: dict[str, Any]
    geometry_type: str
    vertex_count: int
    ring_count: int
    length: float
    area: float
    is_valid: bool
    validity_reason: str
    bounds: tuple[float, float, float, float]


def _finite_coordinates(value: Any) -> bool:
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, (list, tuple)):
        return bool(value) and all(_finite_coordinates(item) for item in value)
    return False


def _consecutive_duplicates(coordinates: Sequence[Sequence[float]]) -> bool:
    return any(a == b for a, b in zip(coordinates, coordinates[1:], strict=False))


def validate_geometry(geojson: dict[str, Any]) -> GeometryAnalysis:
    geometry_type = geojson.get("type")
    if geometry_type not in SUPPORTED_TYPES:
        raise GeometryValidationError(
            f"Unsupported geometry type {geometry_type!r}; expected LineString or Polygon"
        )
    coordinates = geojson.get("coordinates")
    if not isinstance(coordinates, (list, tuple)) or not _finite_coordinates(coordinates):
        raise GeometryValidationError("Coordinates must be non-empty finite numeric arrays")

    if geometry_type == "LineString":
        if len(coordinates) < 2:
            raise GeometryValidationError("A LineString requires at least two coordinates")
        if _consecutive_duplicates(coordinates):
            raise GeometryValidationError("Consecutive duplicate coordinates are not allowed")
    else:
        if not coordinates:
            raise GeometryValidationError("A Polygon requires an exterior ring")
        for ring in coordinates:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise GeometryValidationError(
                    "Every polygon ring must be closed and contain at least four coordinates"
                )
            if _consecutive_duplicates(ring[:-1]):
                raise GeometryValidationError(
                    "Consecutive duplicate ring coordinates are not allowed"
                )

    geometry = shape(geojson)
    if geometry.is_empty:
        raise GeometryValidationError("Geometry must not be empty")
    if not geometry.is_valid:
        raise GeometryValidationError(explain_validity(geometry))

    normalized = mapping(geometry)
    if isinstance(geometry, LineString):
        vertex_count = len(geometry.coords)
        ring_count = 0
    elif isinstance(geometry, Polygon):
        vertex_count = len(geometry.exterior.coords) + sum(
            len(ring.coords) for ring in geometry.interiors
        )
        ring_count = 1 + len(geometry.interiors)
    else:
        raise GeometryValidationError("Geometry normalization produced an unsupported type")

    min_x, min_y, max_x, max_y = geometry.bounds
    return GeometryAnalysis(
        geometry=normalized,
        geometry_type=geometry.geom_type,
        vertex_count=vertex_count,
        ring_count=ring_count,
        length=float(geometry.length),
        area=float(geometry.area),
        is_valid=True,
        validity_reason="Valid Geometry",
        bounds=(float(min_x), float(min_y), float(max_x), float(max_y)),
    )


def analyze_geometry(geojson: dict[str, Any]) -> dict[str, Any]:
    analysis = validate_geometry(geojson)
    return {
        "geometry_type": analysis.geometry_type,
        "vertex_count": analysis.vertex_count,
        "ring_count": analysis.ring_count,
        "length": analysis.length,
        "area": analysis.area,
        "is_valid": analysis.is_valid,
        "validity_reason": analysis.validity_reason,
        "bounds": list(analysis.bounds),
    }


def comparison_metrics(original: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    source = shape(validate_geometry(original).geometry)
    result = shape(validate_geometry(candidate).geometry)
    original_analysis = analyze_geometry(original)
    candidate_analysis = analyze_geometry(candidate)
    return {
        **candidate_analysis,
        "original_vertex_count": original_analysis["vertex_count"],
        "vertex_reduction": 1
        - candidate_analysis["vertex_count"] / original_analysis["vertex_count"],
        "hausdorff_distance": float(hausdorff_distance(source, result)),
        "frechet_distance": float(frechet_distance(source, result)),
        "length_delta": float(result.length - source.length),
        "area_delta": float(result.area - source.area),
    }
