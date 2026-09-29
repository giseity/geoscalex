from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import torch
from shapely import from_wkb
from shapely.geometry import mapping, shape

from geoscalex.geometry.analysis import validate_geometry
from geoscalex.geometry.simplify import build_candidate
from geoscalex.ml.features import consensus_importance, rank_importance, vertex_features
from geoscalex.simplification.keep_move import apply_keep_move, normalize_for_model

TEACHER_RATIOS = (0.1, 0.25, 0.5, 0.75)


@dataclass(frozen=True)
class TrainingSample:
    geometry: dict[str, Any]
    features: np.ndarray
    importance: np.ndarray
    consensus_importance: np.ndarray
    dp_importance: np.ndarray
    vw_importance: np.ndarray
    teacher_method: str
    teacher_normalized_hausdorff: float
    movement: np.ndarray
    movement_mask: np.ndarray
    budget_ratio: float
    split: str


def _read(path: Path) -> list[dict[str, Any]]:
    return pq.read_table(path).to_pylist() if path.exists() else []


def _selected_review_candidates(export_dir: Path) -> set[str]:
    selected: set[str] = set()
    for review in _read(export_dir / "scene_reviews.parquet"):
        if review["acceptability"] != "acceptable":
            continue
        if review["choice"] == "A" and review["candidate_a_id"]:
            selected.add(str(review["candidate_a_id"]))
        elif review["choice"] == "B" and review["candidate_b_id"]:
            selected.add(str(review["candidate_b_id"]))
        elif review["choice"] == "equal":
            selected.update(
                str(candidate_id)
                for candidate_id in (review["candidate_a_id"], review["candidate_b_id"])
                if candidate_id
            )
    return selected


def materialize_importance(
    geometry: dict[str, Any],
    importance: np.ndarray,
    budget: int,
    *,
    fallback_method: str,
) -> tuple[dict[str, Any], bool]:
    normalized = normalize_for_model(geometry)
    kept = select_importance_indices(geometry, importance, budget)
    try:
        candidate, _ = apply_keep_move(
            normalized,
            kept,
            [(0.0, 0.0)] * len(kept),
            budget,
        )
        return candidate, False
    except ValueError:
        candidate, _, _ = build_candidate(geometry, fallback_method, budget=budget)
        return candidate, True


def select_importance_indices(
    geometry: dict[str, Any], importance: np.ndarray, budget: int
) -> list[int]:
    normalized = normalize_for_model(geometry)
    scores = importance.copy()
    if normalized.geometry_type == "LineString":
        protected_score = float(np.max(scores)) + 1.0
        scores[0] = scores[-1] = protected_score
    return sorted(np.argsort(-scores, kind="stable")[:budget].tolist())


def _teacher_quality(
    geometry: dict[str, Any], importance: np.ndarray, method: str
) -> float:
    analysis = validate_geometry(geometry)
    minimum = 3 if analysis.geometry_type == "Polygon" else 2
    min_x, min_y, max_x, max_y = analysis.bounds
    diagonal = max(float(np.hypot(max_x - min_x, max_y - min_y)), 1e-9)
    source_shape = shape(analysis.geometry)
    distances: list[float] = []
    for ratio in TEACHER_RATIOS:
        budget = max(
            minimum,
            min(analysis.vertex_count, int(analysis.vertex_count * ratio + 0.5)),
        )
        candidate, _ = materialize_importance(
            geometry,
            importance,
            budget,
            fallback_method=method,
        )
        distances.append(float(source_shape.hausdorff_distance(shape(candidate))) / diagonal)
    return float(np.mean(distances))


def _select_teacher(
    geometry: dict[str, Any],
    dp_importance: np.ndarray,
    vw_importance: np.ndarray,
) -> tuple[str, np.ndarray, float]:
    qualities = {
        "douglas-peucker": _teacher_quality(
            geometry, dp_importance, "douglas-peucker"
        ),
        "visvalingam-whyatt": _teacher_quality(
            geometry, vw_importance, "visvalingam-whyatt"
        ),
    }
    method = min(qualities, key=lambda name: (qualities[name], name))
    importance = dp_importance if method == "douglas-peucker" else vw_importance
    return method, importance, qualities[method]


def load_samples(
    export_dir: Path, *, split: str | None = None, max_vertices: int = 512
) -> list[TrainingSample]:
    accepted = _selected_review_candidates(export_dir)
    candidates_by_revision: dict[str, list[dict[str, Any]]] = {}
    for candidate in _read(export_dir / "candidates.parquet"):
        if str(candidate["candidate_id"]) in accepted and candidate.get("source_mapping"):
            candidates_by_revision.setdefault(str(candidate["revision_id"]), []).append(candidate)
    samples: list[TrainingSample] = []
    for row in _read(export_dir / "features.parquet"):
        if split is not None and row["split"] != split:
            continue
        geometry = mapping(from_wkb(row["geometry_wkb"]))
        if geometry["type"] == "Polygon" and len(geometry["coordinates"]) != 1:
            continue
        normalized = normalize_for_model(geometry)
        count = len(normalized.coordinates)
        if count > max_vertices:
            continue
        reviewed_candidates = candidates_by_revision.get(str(row["revision_id"]), [])
        candidates: list[dict[str, Any] | None] = (
            [*reviewed_candidates] if reviewed_candidates else [None]
        )
        dp_importance = rank_importance(
            row["dp_scores"], count, protected_value=1.1
        )
        vw_importance = rank_importance(
            row["vw_scores"], count, protected_value=1.1
        )
        consensus = consensus_importance(row["dp_scores"], row["vw_scores"], count)
        teacher_method, importance, teacher_quality = _select_teacher(
            geometry, dp_importance, vw_importance
        )
        for candidate_row in candidates:
            movement = np.zeros((count, 2), dtype=np.float32)
            movement_mask = np.zeros(count, dtype=np.bool_)
            budget_ratio = 0.5
            if candidate_row is not None:
                target = mapping(from_wkb(candidate_row["geometry_wkb"]))
                target_points = (
                    list(target["coordinates"][0][:-1])
                    if target["type"] == "Polygon"
                    else list(target["coordinates"])
                )
                source_mapping = [int(index) for index in candidate_row["source_mapping"]]
                valid_mapping = (
                    len(source_mapping) == len(target_points)
                    and source_mapping == sorted(set(source_mapping))
                    and all(0 <= index < count for index in source_mapping)
                )
                if valid_mapping:
                    for source_index, target_point in zip(
                        source_mapping, target_points, strict=True
                    ):
                        source_point = normalized.source_coordinates[source_index]
                        movement[source_index] = [
                            (target_point[0] - source_point[0]) / normalized.scale,
                            (target_point[1] - source_point[1]) / normalized.scale,
                        ]
                        movement_mask[source_index] = True
                    budget_ratio = len(source_mapping) / count
            samples.append(
                TrainingSample(
                    geometry=geometry,
                    features=vertex_features(normalized),
                    importance=importance,
                    consensus_importance=consensus,
                    dp_importance=dp_importance,
                    vw_importance=vw_importance,
                    teacher_method=teacher_method,
                    teacher_normalized_hausdorff=teacher_quality,
                    movement=movement,
                    movement_mask=movement_mask,
                    budget_ratio=budget_ratio,
                    split=str(row["split"]),
                )
            )
    return samples


def collate(
    samples: list[TrainingSample], *, importance_ratios: list[float] | None = None
) -> dict[str, torch.Tensor]:
    if importance_ratios is not None and len(importance_ratios) != len(samples):
        raise ValueError("importance_ratios must match the sample count")
    batch_size = len(samples)
    maximum = max(len(sample.features) for sample in samples)
    feature_dim = samples[0].features.shape[1]
    features = torch.zeros((batch_size, maximum, feature_dim), dtype=torch.float32)
    importance = torch.zeros((batch_size, maximum), dtype=torch.float32)
    keep_mask = torch.zeros((batch_size, maximum), dtype=torch.bool)
    movement = torch.zeros((batch_size, maximum, 2), dtype=torch.float32)
    padding_mask = torch.ones((batch_size, maximum), dtype=torch.bool)
    movement_mask = torch.zeros((batch_size, maximum), dtype=torch.bool)
    ratios = torch.zeros(batch_size, dtype=torch.float32)
    for index, sample in enumerate(samples):
        count = len(sample.features)
        features[index, :count] = torch.from_numpy(sample.features)
        importance[index, :count] = torch.from_numpy(sample.importance)
        movement[index, :count] = torch.from_numpy(sample.movement)
        padding_mask[index, :count] = False
        movement_mask[index, :count] = torch.from_numpy(sample.movement_mask)
        ratio = (
            sample.budget_ratio
            if sample.movement_mask.any() or importance_ratios is None
            else importance_ratios[index]
        )
        minimum = 3 if sample.geometry["type"] == "Polygon" else 2
        budget = max(minimum, min(count, int(count * ratio + 0.5)))
        selected = select_importance_indices(sample.geometry, sample.importance, budget)
        keep_mask[index, selected] = True
        ratios[index] = ratio
    return {
        "features": features,
        "importance": importance,
        "keep_mask": keep_mask,
        "movement": movement,
        "padding_mask": padding_mask,
        "movement_mask": movement_mask,
        "budget_ratio": ratios,
    }
