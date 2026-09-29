from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
import torch
from shapely import from_wkb
from shapely.geometry import mapping

from geoscalex.ml.features import consensus_importance, vertex_features
from geoscalex.simplification.keep_move import normalize_for_model


@dataclass(frozen=True)
class TrainingSample:
    geometry: dict[str, Any]
    features: np.ndarray
    importance: np.ndarray
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
                    importance=consensus_importance(row["dp_scores"], row["vw_scores"], count),
                    movement=movement,
                    movement_mask=movement_mask,
                    budget_ratio=budget_ratio,
                    split=str(row["split"]),
                )
            )
    return samples


def collate(samples: list[TrainingSample]) -> dict[str, torch.Tensor]:
    batch_size = len(samples)
    maximum = max(len(sample.features) for sample in samples)
    feature_dim = samples[0].features.shape[1]
    features = torch.zeros((batch_size, maximum, feature_dim), dtype=torch.float32)
    importance = torch.zeros((batch_size, maximum), dtype=torch.float32)
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
        ratios[index] = sample.budget_ratio
    return {
        "features": features,
        "importance": importance,
        "movement": movement,
        "padding_mask": padding_mask,
        "movement_mask": movement_mask,
        "budget_ratio": ratios,
    }
