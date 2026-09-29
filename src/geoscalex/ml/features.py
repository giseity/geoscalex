from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray

from geoscalex.simplification.keep_move import NormalizedGeometry

FEATURE_DIM = 12


def vertex_features(geometry: NormalizedGeometry) -> NDArray[np.float32]:
    points = np.asarray(geometry.coordinates, dtype=np.float32)
    count = len(points)
    polygon = geometry.geometry_type == "Polygon"
    rows: list[list[float]] = []
    cumulative = [0.0]
    for index in range(1, count):
        cumulative.append(cumulative[-1] + float(np.linalg.norm(points[index] - points[index - 1])))
    total = max(cumulative[-1], 1e-9)
    for index, point in enumerate(points):
        previous_index = (index - 1) % count if polygon else max(0, index - 1)
        next_index = (index + 1) % count if polygon else min(count - 1, index + 1)
        previous = points[index] - points[previous_index]
        following = points[next_index] - points[index]
        previous_length = float(np.linalg.norm(previous))
        following_length = float(np.linalg.norm(following))
        cross = float(previous[0] * following[1] - previous[1] * following[0])
        dot = float(previous[0] * following[0] + previous[1] * following[1])
        angle = math.atan2(cross, dot)
        endpoint = float(not polygon and index in {0, count - 1})
        rows.append(
            [
                float(point[0]),
                float(point[1]),
                float(previous[0]),
                float(previous[1]),
                float(following[0]),
                float(following[1]),
                previous_length,
                following_length,
                math.sin(angle),
                math.cos(angle),
                cumulative[index] / total,
                endpoint if not polygon else -1.0,
            ]
        )
    return np.asarray(rows, dtype=np.float32)


def consensus_importance(
    dp_scores: list[float | None], vw_scores: list[float | None], count: int
) -> NDArray[np.float32]:
    def ranks(values: list[float | None]) -> NDArray[np.float32]:
        trimmed = values[:count]
        finite = np.asarray([float(value or 0.0) for value in trimmed], dtype=np.float64)
        order = np.argsort(np.argsort(finite, kind="stable"), kind="stable")
        ranked = (order.astype(np.float32) / max(count - 1, 1)).astype(np.float32)
        for index, value in enumerate(trimmed):
            if value is None:
                ranked[index] = 1.0
        return ranked

    consensus = ((ranks(dp_scores) + ranks(vw_scores)) / 2).astype(np.float32)
    return consensus
