from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Any

from shapely.geometry import Polygon

from geoscalex.geometry.analysis import GeometryValidationError, comparison_metrics, validate_geometry

Point = tuple[float, float]


@dataclass(frozen=True)
class Hierarchy:
    scores: list[float]
    protected: list[bool]
    ring_lengths: list[int]


def _distance_to_segment(point: Point, start: Point, end: Point) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    if dx == 0 and dy == 0:
        return math.dist(point, start)
    t = max(0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (dx * dx + dy * dy)))
    projection = (start[0] + t * dx, start[1] + t * dy)
    return math.dist(point, projection)


def _dp_open(points: list[Point]) -> list[float]:
    scores = [0.0] * len(points)
    scores[0] = scores[-1] = math.inf

    def visit(start: int, end: int, ceiling: float) -> None:
        if end <= start + 1:
            return
        distances = [
            (_distance_to_segment(points[index], points[start], points[end]), index)
            for index in range(start + 1, end)
        ]
        distance, pivot = max(distances, key=lambda item: (item[0], -item[1]))
        effective = min(distance, ceiling)
        scores[pivot] = max(scores[pivot], effective)
        visit(start, pivot, effective)
        visit(pivot, end, effective)

    visit(0, len(points) - 1, math.inf)
    return scores


def _farthest_pair(points: list[Point]) -> tuple[int, int]:
    best = (-1.0, 0, 1)
    for left in range(len(points)):
        for right in range(left + 1, len(points)):
            distance = (points[left][0] - points[right][0]) ** 2 + (
                points[left][1] - points[right][1]
            ) ** 2
            candidate = (distance, -left, -right)
            if candidate > (best[0], -best[1], -best[2]):
                best = (distance, left, right)
    return best[1], best[2]


def _dp_ring(closed_points: list[Point]) -> list[float]:
    points = closed_points[:-1]
    left, right = _farthest_pair(points)
    chain_a = points[left : right + 1]
    chain_b = points[right:] + points[: left + 1]
    scores = [0.0] * len(points)
    for index, score in zip(range(left, right + 1), _dp_open(chain_a), strict=True):
        scores[index] = max(scores[index], score)
    indices_b = list(range(right, len(points))) + list(range(0, left + 1))
    for index, score in zip(indices_b, _dp_open(chain_b), strict=True):
        scores[index] = max(scores[index], score)
    return scores + [scores[0]]


def _triangle_area(a: Point, b: Point, c: Point) -> float:
    return abs((a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1])) / 2)


def _vw_open(points: list[Point]) -> list[float]:
    count = len(points)
    scores = [math.inf] + [0.0] * (count - 2) + [math.inf]
    previous = [index - 1 for index in range(count)]
    following = [index + 1 for index in range(count)]
    removed = [False] * count
    versions = [0] * count
    heap: list[tuple[float, int, int]] = []

    def push(index: int) -> None:
        if index <= 0 or index >= count - 1 or removed[index]:
            return
        area = _triangle_area(points[previous[index]], points[index], points[following[index]])
        versions[index] += 1
        heapq.heappush(heap, (area, index, versions[index]))

    for index in range(1, count - 1):
        push(index)
    floor = 0.0
    while heap:
        area, index, version = heapq.heappop(heap)
        if removed[index] or version != versions[index]:
            continue
        floor = max(floor, area)
        scores[index] = floor
        removed[index] = True
        left, right = previous[index], following[index]
        following[left] = right
        previous[right] = left
        push(left)
        push(right)
    return scores


def _vw_ring(closed_points: list[Point]) -> list[float]:
    points = closed_points[:-1]
    count = len(points)
    scores = [0.0] * count
    previous = [(index - 1) % count for index in range(count)]
    following = [(index + 1) % count for index in range(count)]
    removed = [False] * count
    versions = [0] * count
    heap: list[tuple[float, int, int]] = []

    def push(index: int) -> None:
        if removed[index]:
            return
        area = _triangle_area(points[previous[index]], points[index], points[following[index]])
        versions[index] += 1
        heapq.heappush(heap, (area, index, versions[index]))

    for index in range(count):
        push(index)
    floor = 0.0
    remaining = count
    while heap and remaining > 3:
        area, index, version = heapq.heappop(heap)
        if removed[index] or version != versions[index]:
            continue
        floor = max(floor, area)
        scores[index] = floor
        removed[index] = True
        remaining -= 1
        left, right = previous[index], following[index]
        following[left] = right
        previous[right] = left
        push(left)
        push(right)
    for index in range(count):
        if not removed[index]:
            scores[index] = math.inf
    return scores + [scores[0]]


def _rings(geometry: dict[str, Any]) -> list[list[Point]]:
    if geometry["type"] == "LineString":
        return [[tuple(point) for point in geometry["coordinates"]]]
    return [[tuple(point) for point in ring] for ring in geometry["coordinates"]]


def hierarchy_scores(geometry: dict[str, Any], method: str) -> Hierarchy:
    normalized = validate_geometry(geometry).geometry
    rings = _rings(normalized)
    all_scores: list[float] = []
    protected: list[bool] = []
    for ring_index, ring in enumerate(rings):
        closed = normalized["type"] == "Polygon"
        if method == "douglas-peucker":
            scores = _dp_ring(ring) if closed else _dp_open(ring)
        elif method == "visvalingam-whyatt":
            scores = _vw_ring(ring) if closed else _vw_open(ring)
        else:
            raise ValueError(f"Unknown simplification method: {method}")
        all_scores.extend(scores)
        protected.extend(math.isinf(score) for score in scores)
    return Hierarchy(all_scores, protected, [len(ring) for ring in rings])


def _selected_indices(scores: list[float], tolerance: float | None, budget: int | None) -> set[int]:
    if budget is not None:
        ordered = sorted(range(len(scores)), key=lambda index: (-scores[index], index))
        return set(ordered[: max(2, min(budget, len(scores)))])
    threshold = tolerance or 0.0
    return {index for index, score in enumerate(scores) if score >= threshold}


def _candidate_from_selection(
    geometry: dict[str, Any], hierarchy: Hierarchy, selected: set[int]
) -> dict[str, Any]:
    cursor = 0
    output_rings: list[list[list[float]]] = []
    for ring_index, ring in enumerate(_rings(geometry)):
        ring_indices = list(range(cursor, cursor + len(ring)))
        cursor += len(ring)
        if geometry["type"] == "LineString":
            kept = [list(point) for index, point in zip(ring_indices, ring, strict=True) if index in selected]
            return {"type": "LineString", "coordinates": kept}

        unique = ring[:-1]
        unique_indices = ring_indices[:-1]
        kept = [
            list(point)
            for index, point in zip(unique_indices, unique, strict=True)
            if index in selected
        ]
        if len(kept) < 3:
            ranked = sorted(unique_indices, key=lambda index: (-hierarchy.scores[index], index))
            required = set(ranked[:3])
            kept = [
                list(point)
                for index, point in zip(unique_indices, unique, strict=True)
                if index in required
            ]
        kept.append(kept[0])
        output_rings.append(kept)
    return {"type": "Polygon", "coordinates": output_rings}


def build_candidate(
    geometry: dict[str, Any], method: str, *, tolerance: float | None = None, budget: int | None = None
) -> tuple[dict[str, Any], Hierarchy, dict[str, Any]]:
    normalized = validate_geometry(geometry).geometry
    hierarchy = hierarchy_scores(normalized, method)
    selected = _selected_indices(hierarchy.scores, tolerance, budget)
    selected.update(index for index, value in enumerate(hierarchy.protected) if value)

    candidate = _candidate_from_selection(normalized, hierarchy, selected)
    if normalized["type"] == "Polygon":
        removable = sorted(
            (index for index in range(len(hierarchy.scores)) if index not in selected),
            key=lambda index: (-hierarchy.scores[index], index),
        )
        while True:
            try:
                validate_geometry(candidate)
                break
            except GeometryValidationError:
                if not removable:
                    candidate = normalized
                    break
                selected.add(removable.pop(0))
                candidate = _candidate_from_selection(normalized, hierarchy, selected)
    metrics = comparison_metrics(normalized, candidate)
    return candidate, hierarchy, metrics


def add_polygon_hole(polygon: dict[str, Any], hole: dict[str, Any]) -> dict[str, Any]:
    parent = validate_geometry(polygon)
    cutter = validate_geometry(hole)
    if parent.geometry_type != "Polygon" or cutter.geometry_type != "Polygon":
        raise GeometryValidationError("Hole operations require two polygons")
    parent_shape = Polygon(parent.geometry["coordinates"][0], parent.geometry["coordinates"][1:])
    cutter_shape = Polygon(cutter.geometry["coordinates"][0], cutter.geometry["coordinates"][1:])
    if not parent_shape.contains(cutter_shape):
        raise GeometryValidationError("A hole must be strictly contained by the exterior polygon")
    result = parent_shape.difference(cutter_shape)
    if result.geom_type != "Polygon":
        raise GeometryValidationError("The hole operation would create a multipart polygon")
    return validate_geometry(result.__geo_interface__).geometry
