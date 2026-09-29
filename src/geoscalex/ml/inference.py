from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import torch

from geoscalex.geometry.simplify import build_candidate
from geoscalex.ml.features import vertex_features
from geoscalex.ml.model import ModelConfig, RemoveMoveEncoder
from geoscalex.simplification.keep_move import apply_keep_move, normalize_for_model


@lru_cache(maxsize=2)
def load_checkpoint(path: Path, device: str = "cpu") -> tuple[RemoveMoveEncoder, dict[str, Any]]:
    payload: dict[str, Any] = torch.load(path, map_location=device, weights_only=True)
    model = RemoveMoveEncoder(ModelConfig(**payload["model_config"]))
    model.load_state_dict(payload["model_state"])
    model.to(device)
    model.eval()
    return model, payload.get("metadata", {})


def checkpoint_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def infer_geometry(
    model: RemoveMoveEncoder,
    geometry: dict[str, Any],
    budget: int,
    *,
    device: str = "cpu",
) -> tuple[dict[str, Any], list[int], list[float], dict[str, Any], dict[str, float]]:
    normalized = normalize_for_model(geometry)
    matrix = vertex_features(normalized)
    features = torch.from_numpy(matrix)[None].to(device)
    padding_mask = torch.zeros((1, len(matrix)), dtype=torch.bool, device=device)
    ratio = torch.tensor([budget / len(matrix)], dtype=torch.float32, device=device)
    with torch.no_grad():
        importance, displacement = model(features, padding_mask, ratio)
    scores = importance[0].cpu().numpy()
    offsets = displacement[0].cpu().numpy()
    if normalized.geometry_type == "LineString":
        protected_score = float(np.max(scores)) + 1.0
        scores[0] = scores[-1] = protected_score
    kept = sorted(np.argsort(-scores, kind="stable")[:budget].tolist())
    selected_offsets = [tuple(float(value) for value in offsets[index]) for index in kept]
    validation_errors: list[str] = []
    for scale in (1.0, 0.5, 0.25, 0.0):
        scaled = [(dx * scale, dy * scale) for dx, dy in selected_offsets]
        if normalized.geometry_type == "LineString":
            scaled[0] = scaled[-1] = (0.0, 0.0)
        try:
            candidate, movement = apply_keep_move(normalized, kept, scaled, budget)
            return (
                candidate,
                kept,
                [float(value) for value in scores],
                {
                    "fallback_used": False,
                    "displacement_scale": scale,
                    "validation_errors": validation_errors,
                },
                movement,
            )
        except ValueError as error:
            validation_errors.append(str(error))
    candidate, _, _ = build_candidate(geometry, "visvalingam-whyatt", budget=budget)
    fallback_normalized = normalize_for_model(candidate)
    fallback_mapping: list[int] = []
    for point in fallback_normalized.source_coordinates:
        fallback_mapping.append(normalized.source_coordinates.index(point))
    return (
        candidate,
        fallback_mapping,
        [float(value) for value in scores],
        {
            "fallback_used": True,
            "fallback_method": "visvalingam-whyatt",
            "validation_errors": validation_errors,
        },
        {"moved_vertex_count": 0.0, "maximum_displacement": 0.0, "mean_displacement": 0.0},
    )
