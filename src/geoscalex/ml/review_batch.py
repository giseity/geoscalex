from __future__ import annotations

import argparse
import asyncio
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from shapely.geometry import mapping

from geoscalex.domain import SceneExtractionCreate, SceneRegion
from geoscalex.geometry.analysis import comparison_metrics, validate_geometry
from geoscalex.geometry.simplify import hierarchy_scores
from geoscalex.ml.data import (
    materialize_importance,
    select_importance_indices,
    select_quality_teacher,
)
from geoscalex.ml.features import rank_importance
from geoscalex.ml.inference import checkpoint_hash, infer_geometry, load_checkpoint
from geoscalex.ml.model import RemoveMoveEncoder
from geoscalex.scenes.extraction import build_extraction_plan, load_extraction_features
from geoscalex.simplification.keep_move import normalize_for_model
from geoscalex.storage import repository
from geoscalex.storage.db import Session, init_database


@dataclass(frozen=True)
class ReviewPriority:
    feature_id: str
    feature_name: str
    priority: float
    mean_topk_disagreement: float
    mean_quality_gap: float
    ratios: list[dict[str, Any]]


def score_review_priority(
    model: RemoveMoveEncoder,
    geometry: dict[str, Any],
    *,
    feature_id: str,
    feature_name: str,
    ratios: tuple[float, ...] = (0.1, 0.25),
    device: str = "cpu",
) -> ReviewPriority:
    """Score a geometry by where the encoder most needs human supervision."""
    if not ratios or any(ratio <= 0 or ratio > 1 for ratio in ratios):
        raise ValueError("Review ratios must be values in (0, 1]")
    analysis = validate_geometry(geometry)
    normalized = normalize_for_model(geometry)
    count = len(normalized.coordinates)
    dp = hierarchy_scores(geometry, "douglas-peucker")
    vw = hierarchy_scores(geometry, "visvalingam-whyatt")
    dp_importance = rank_importance(
        [None if math.isinf(value) else value for value in dp.scores],
        count,
        protected_value=1.1,
    )
    vw_importance = rank_importance(
        [None if math.isinf(value) else value for value in vw.scores],
        count,
        protected_value=1.1,
    )
    teacher_method, teacher_importance, _ = select_quality_teacher(
        geometry, dp_importance, vw_importance
    )
    min_x, min_y, max_x, max_y = analysis.bounds
    diagonal = max(math.hypot(max_x - min_x, max_y - min_y), 1e-9)
    minimum = 3 if geometry["type"] == "Polygon" else 2
    components: list[dict[str, Any]] = []
    for ratio in ratios:
        budget = max(minimum, min(count, int(count * ratio + 0.5)))
        encoder_candidate, encoder_kept, _, diagnostics, _ = infer_geometry(
            model, geometry, budget, device=device
        )
        teacher_candidate, teacher_fallback = materialize_importance(
            geometry,
            teacher_importance,
            budget,
            fallback_method=teacher_method,
        )
        teacher_kept = set(select_importance_indices(geometry, teacher_importance, budget))
        agreement = len(set(encoder_kept).intersection(teacher_kept)) / budget
        encoder_distance = (
            float(comparison_metrics(geometry, encoder_candidate)["hausdorff_distance"]) / diagonal
        )
        teacher_distance = (
            float(comparison_metrics(geometry, teacher_candidate)["hausdorff_distance"]) / diagonal
        )
        quality_gap = max(0.0, encoder_distance - teacher_distance)
        components.append(
            {
                "retention_ratio": ratio,
                "vertex_budget": budget,
                "topk_agreement": agreement,
                "topk_disagreement": 1.0 - agreement,
                "encoder_normalized_hausdorff": encoder_distance,
                "teacher_normalized_hausdorff": teacher_distance,
                "quality_gap": quality_gap,
                "teacher_method": teacher_method,
                "encoder_fallback_used": bool(diagnostics["fallback_used"]),
                "teacher_fallback_used": teacher_fallback,
            }
        )
    disagreement = sum(float(item["topk_disagreement"]) for item in components) / len(components)
    quality_gap = sum(float(item["quality_gap"]) for item in components) / len(components)
    return ReviewPriority(
        feature_id=feature_id,
        feature_name=feature_name,
        priority=disagreement + quality_gap,
        mean_topk_disagreement=disagreement,
        mean_quality_gap=quality_gap,
        ratios=components,
    )


async def build_review_batch(
    dataset_id: UUID,
    checkpoint: Path,
    *,
    target_batch_id: UUID | None = None,
    max_targets: int = 100,
    max_vertices: int = 512,
    max_candidates: int = 5_000,
    ratios: tuple[float, ...] = (0.1, 0.25),
    device: str = "cpu",
    create: bool = False,
) -> dict[str, Any]:
    model, checkpoint_metadata = load_checkpoint(checkpoint, device)
    digest = checkpoint_hash(checkpoint)
    await init_database()
    async with Session() as session:
        features, incompatible = await load_extraction_features(session, str(dataset_id))
        eligible = [
            feature
            for feature in features
            if target_batch_id is None or feature.batch_id == str(target_batch_id)
        ]
        scores: list[ReviewPriority] = []
        skipped: list[dict[str, str]] = []
        for feature in eligible[:max_candidates]:
            geometry = mapping(feature.geometry)
            try:
                normalized = normalize_for_model(geometry)
                if len(normalized.coordinates) > max_vertices:
                    raise ValueError(f"more than {max_vertices} model vertices")
                scores.append(
                    score_review_priority(
                        model,
                        geometry,
                        feature_id=feature.id,
                        feature_name=feature.name,
                        ratios=ratios,
                        device=device,
                    )
                )
            except ValueError as error:
                skipped.append({"feature_id": feature.id, "reason": str(error)})
        scores.sort(key=lambda item: (-item.priority, item.feature_id))
        selected = scores[:max_targets]
        config = SceneExtractionCreate(
            dataset_id=dataset_id,
            target_batch_id=target_batch_id,
            target_feature_ids=[UUID(item.feature_id) for item in selected],
            region=SceneRegion.NORTH_AMERICA,
            location_group_prefix="review-priority-v0.7",
            max_scenes=max_targets,
        )
        plan = await build_extraction_plan(session, config)
        by_id = {item.feature_id: item for item in selected}
        scene_ids: list[str] = []
        if create:
            for planned in plan.scenes:
                score = by_id[str(planned.proposal.target_feature_id)]
                planned.create.provenance["review_priority"] = {
                    **asdict(score),
                    "checkpoint_sha256": digest,
                }
                scene = await repository.create_scene(session, planned.create)
                scene_ids.append(str(scene.id))
    return {
        "format_version": 1,
        "dataset_id": str(dataset_id),
        "target_batch_id": str(target_batch_id) if target_batch_id else None,
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_sha256": digest,
        "checkpoint_metadata": checkpoint_metadata,
        "retention_ratios": ratios,
        "eligible_features": len(eligible),
        "scored_features": len(scores),
        "incompatible_features": incompatible,
        "skipped_features": skipped,
        "selected": [asdict(item) for item in selected],
        "planned_scenes": len(plan.scenes),
        "isolated_targets": plan.isolated_targets,
        "created_scene_ids": scene_ids,
    }


def run() -> None:
    parser = argparse.ArgumentParser(
        description="Rank imported features for human review and optionally create scenes"
    )
    parser.add_argument("dataset_id", type=UUID)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--target-batch-id", type=UUID)
    parser.add_argument("--max-targets", type=int, default=100)
    parser.add_argument("--max-vertices", type=int, default=512)
    parser.add_argument("--max-candidates", type=int, default=5_000)
    parser.add_argument("--ratios", type=float, nargs="+", default=[0.1, 0.25])
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.max_targets < 1 or arguments.max_candidates < 1:
        parser.error("--max-targets and --max-candidates must be positive")
    report = asyncio.run(
        build_review_batch(
            arguments.dataset_id,
            arguments.checkpoint,
            target_batch_id=arguments.target_batch_id,
            max_targets=arguments.max_targets,
            max_vertices=arguments.max_vertices,
            max_candidates=arguments.max_candidates,
            ratios=tuple(arguments.ratios),
            device=arguments.device,
            create=arguments.create,
        )
    )
    rendered = json.dumps(report, indent=2)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    run()
