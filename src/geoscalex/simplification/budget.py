from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from geoscalex.domain import RetentionRatioBudget, SimplificationBudget, VertexCountBudget
from geoscalex.geometry.analysis import validate_geometry


@dataclass(frozen=True)
class ResolvedBudget:
    requested: dict[str, Any]
    vertex_count: int
    source_vertex_count: int
    minimum_vertex_count: int


def resolve_budget(geometry: dict[str, Any], budget: SimplificationBudget) -> ResolvedBudget:
    analysis = validate_geometry(geometry)
    minimum = 3 * analysis.ring_count if analysis.geometry_type == "Polygon" else 2
    source_count = analysis.vertex_count
    if isinstance(budget, VertexCountBudget):
        resolved = budget.value
    elif isinstance(budget, RetentionRatioBudget):
        resolved = math.floor(source_count * budget.value + 0.5)
    else:  # pragma: no cover - the API union prevents this
        raise TypeError("Unsupported simplification budget")
    resolved = max(minimum, min(resolved, source_count))
    return ResolvedBudget(
        requested=budget.model_dump(mode="json"),
        vertex_count=resolved,
        source_vertex_count=source_count,
        minimum_vertex_count=minimum,
    )
