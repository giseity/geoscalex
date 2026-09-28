import math

import pytest

from geoscalex.geometry.analysis import GeometryValidationError, validate_geometry
from geoscalex.geometry.simplify import add_polygon_hole, build_candidate, hierarchy_scores


LINE = {
    "type": "LineString",
    "coordinates": [[0, 0], [1, 0.1], [2, 2], [3, 0.1], [4, 0]],
}


def test_line_hierarchies_protect_endpoints() -> None:
    for method in ("douglas-peucker", "visvalingam-whyatt"):
        hierarchy = hierarchy_scores(LINE, method)
        assert math.isinf(hierarchy.scores[0])
        assert math.isinf(hierarchy.scores[-1])
        candidate, _, metrics = build_candidate(LINE, method, budget=3)
        assert len(candidate["coordinates"]) == 3
        assert metrics["vertex_reduction"] == pytest.approx(0.4)


def test_polygon_hole_creation_and_simplification_stays_valid() -> None:
    exterior = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [5, 0], [6, 2], [5, 5], [0, 5], [0, 0]]],
    }
    hole = {
        "type": "Polygon",
        "coordinates": [[[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]]],
    }
    polygon = add_polygon_hole(exterior, hole)
    assert len(polygon["coordinates"]) == 2
    candidate, _, _ = build_candidate(polygon, "visvalingam-whyatt", budget=8)
    assert validate_geometry(candidate).is_valid


def test_rejects_self_intersection() -> None:
    with pytest.raises(GeometryValidationError):
        validate_geometry(
            {
                "type": "Polygon",
                "coordinates": [[[0, 0], [2, 2], [0, 2], [2, 0], [0, 0]]],
            }
        )
