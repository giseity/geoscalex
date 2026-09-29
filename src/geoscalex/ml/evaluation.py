from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

import numpy as np

from geoscalex.geometry.analysis import comparison_metrics, validate_geometry
from geoscalex.geometry.simplify import build_candidate
from geoscalex.ml.data import TrainingSample, load_samples
from geoscalex.ml.inference import infer_geometry, load_checkpoint
from geoscalex.simplification.keep_move import apply_keep_move, normalize_for_model


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latency = [float(row["latency_ms"]) for row in rows]
    polygon_rows = [row for row in rows if "intersection_over_union" in row]
    return {
        "candidate_count": len(rows),
        "validity_rate": _mean([float(row["is_valid"]) for row in rows]),
        "budget_satisfaction_rate": _mean([float(row["budget_satisfied"]) for row in rows]),
        "fallback_rate": _mean([float(row.get("fallback_used", False)) for row in rows]),
        "mean_hausdorff_distance": _mean([float(row["hausdorff_distance"]) for row in rows]),
        "mean_normalized_hausdorff_distance": _mean(
            [float(row["normalized_hausdorff_distance"]) for row in rows]
        ),
        "mean_frechet_distance": _mean([float(row["frechet_distance"]) for row in rows]),
        "mean_absolute_normalized_length_delta": _mean(
            [float(row["absolute_normalized_length_delta"]) for row in rows]
        ),
        "mean_intersection_over_union": (
            _mean([float(row["intersection_over_union"]) for row in polygon_rows])
            if polygon_rows
            else None
        ),
        "mean_latency_ms": _mean(latency),
        "median_latency_ms": float(np.quantile(latency, 0.5)) if latency else 0.0,
        "p95_latency_ms": float(np.quantile(latency, 0.95)) if latency else 0.0,
    }


def _paired_summary(
    encoder_rows: list[dict[str, Any]], baseline_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(encoder_rows) != len(baseline_rows):
        raise ValueError("Paired evaluation rows must have equal lengths")
    tolerance = 1e-12
    hausdorff_deltas = [
        float(encoder["normalized_hausdorff_distance"])
        - float(baseline["normalized_hausdorff_distance"])
        for encoder, baseline in zip(encoder_rows, baseline_rows, strict=True)
    ]
    polygon_iou_deltas = [
        float(encoder["intersection_over_union"])
        - float(baseline["intersection_over_union"])
        for encoder, baseline in zip(encoder_rows, baseline_rows, strict=True)
        if "intersection_over_union" in encoder and "intersection_over_union" in baseline
    ]
    count = len(hausdorff_deltas)
    return {
        "pair_count": count,
        "encoder_hausdorff_win_rate": (
            _mean([float(delta < -tolerance) for delta in hausdorff_deltas])
        ),
        "encoder_hausdorff_tie_rate": (
            _mean([float(abs(delta) <= tolerance) for delta in hausdorff_deltas])
        ),
        "encoder_hausdorff_loss_rate": (
            _mean([float(delta > tolerance) for delta in hausdorff_deltas])
        ),
        "mean_encoder_minus_baseline_normalized_hausdorff": _mean(hausdorff_deltas),
        "polygon_pair_count": len(polygon_iou_deltas),
        "encoder_polygon_iou_win_rate": (
            _mean([float(delta > tolerance) for delta in polygon_iou_deltas])
            if polygon_iou_deltas
            else None
        ),
        "mean_encoder_minus_baseline_polygon_iou": (
            _mean(polygon_iou_deltas) if polygon_iou_deltas else None
        ),
    }


def _teacher_candidate(
    sample: TrainingSample, budget: int
) -> tuple[dict[str, Any], bool]:
    """Materialize the exact ranking target without asking the encoder to imitate it."""
    normalized = normalize_for_model(sample.geometry)
    scores = sample.importance.copy()
    if normalized.geometry_type == "LineString":
        protected_score = float(np.max(scores)) + 1.0
        scores[0] = scores[-1] = protected_score
    kept = sorted(np.argsort(-scores, kind="stable")[:budget].tolist())
    try:
        candidate, _ = apply_keep_move(
            normalized,
            kept,
            [(0.0, 0.0)] * len(kept),
            budget,
        )
        return candidate, False
    except ValueError:
        candidate, _, _ = build_candidate(
            sample.geometry, "visvalingam-whyatt", budget=budget
        )
        return candidate, True


def _renamed_pair_summary(
    candidate_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    *,
    candidate_name: str,
) -> dict[str, Any]:
    return {
        key.replace("encoder", candidate_name): value
        for key, value in _paired_summary(candidate_rows, baseline_rows).items()
    }


def evaluate(
    export_dir: Path,
    checkpoint: Path,
    *,
    split: str = "test",
    device: str = "cpu",
    ratios: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75),
) -> dict[str, Any]:
    ratios = tuple(sorted(set(ratios)))
    if not ratios or any(ratio <= 0 or ratio > 1 for ratio in ratios):
        raise ValueError("Evaluation ratios must be unique values in (0, 1]")
    requested_split = split
    samples = load_samples(export_dir, split=split)
    split_fallback = False
    if not samples and split == "test":
        samples = load_samples(export_dir, split="validation")
        split = "validation"
        split_fallback = True
    if not samples and requested_split == "test":
        samples = load_samples(export_dir, split="train")
        split = "train"
        split_fallback = True
    if not samples:
        raise ValueError(f"No {split} samples found in {export_dir}")
    model, metadata = load_checkpoint(checkpoint, device)
    warmup_sample = samples[0]
    warmup_count = validate_geometry(warmup_sample.geometry).vertex_count
    warmup_minimum = 3 if warmup_sample.geometry["type"] == "Polygon" else 2
    warmup_budget = max(
        warmup_minimum, min(warmup_count, int(warmup_count * ratios[0] + 0.5))
    )
    cold_start = time.perf_counter()
    infer_geometry(model, warmup_sample.geometry, warmup_budget, device=device)
    encoder_cold_start_latency_ms = (time.perf_counter() - cold_start) * 1000
    measurements: dict[str, list[dict[str, Any]]] = {
        "encoder-remove-move": [],
        "teacher-consensus-oracle": [],
        "douglas-peucker": [],
        "visvalingam-whyatt": [],
    }
    for sample in samples:
        source_analysis = validate_geometry(sample.geometry)
        source_count = source_analysis.vertex_count
        min_x, min_y, max_x, max_y = source_analysis.bounds
        diagonal = max(math.hypot(max_x - min_x, max_y - min_y), 1e-9)
        minimum = 3 if sample.geometry["type"] == "Polygon" else 2
        for ratio in ratios:
            budget = max(minimum, min(source_count, int(source_count * ratio + 0.5)))
            started = time.perf_counter()
            candidate, _, _, diagnostics, _ = infer_geometry(
                model, sample.geometry, budget, device=device
            )
            encoder_metrics = comparison_metrics(sample.geometry, candidate)
            encoder_metrics["normalized_hausdorff_distance"] = (
                encoder_metrics["hausdorff_distance"] / diagonal
            )
            encoder_metrics["latency_ms"] = (time.perf_counter() - started) * 1000
            encoder_metrics["budget_satisfied"] = encoder_metrics["vertex_count"] == budget
            encoder_metrics["fallback_used"] = bool(diagnostics["fallback_used"])
            encoder_metrics["retention_ratio"] = ratio
            encoder_metrics["geometry_type"] = sample.geometry["type"]
            encoder_metrics["absolute_normalized_length_delta"] = abs(
                encoder_metrics["length_delta"]
            ) / max(source_analysis.length, 1e-9)
            measurements["encoder-remove-move"].append(encoder_metrics)
            started = time.perf_counter()
            teacher_candidate, teacher_fallback = _teacher_candidate(sample, budget)
            teacher_metrics = comparison_metrics(sample.geometry, teacher_candidate)
            teacher_metrics["normalized_hausdorff_distance"] = (
                teacher_metrics["hausdorff_distance"] / diagonal
            )
            teacher_metrics["latency_ms"] = (time.perf_counter() - started) * 1000
            teacher_metrics["budget_satisfied"] = teacher_metrics["vertex_count"] == budget
            teacher_metrics["fallback_used"] = teacher_fallback
            teacher_metrics["retention_ratio"] = ratio
            teacher_metrics["geometry_type"] = sample.geometry["type"]
            teacher_metrics["absolute_normalized_length_delta"] = abs(
                teacher_metrics["length_delta"]
            ) / max(source_analysis.length, 1e-9)
            measurements["teacher-consensus-oracle"].append(teacher_metrics)
            for method in ("douglas-peucker", "visvalingam-whyatt"):
                started = time.perf_counter()
                classical, _, _ = build_candidate(sample.geometry, method, budget=budget)
                metrics = comparison_metrics(sample.geometry, classical)
                metrics["normalized_hausdorff_distance"] = metrics["hausdorff_distance"] / diagonal
                metrics["latency_ms"] = (time.perf_counter() - started) * 1000
                metrics["budget_satisfied"] = metrics["vertex_count"] == budget
                metrics["fallback_used"] = False
                metrics["retention_ratio"] = ratio
                metrics["geometry_type"] = sample.geometry["type"]
                metrics["absolute_normalized_length_delta"] = abs(metrics["length_delta"]) / max(
                    source_analysis.length, 1e-9
                )
                measurements[method].append(metrics)

    methods: dict[str, Any] = {}
    for name, rows in measurements.items():
        methods[name] = _summary(rows)
        methods[name]["by_retention_ratio"] = {
            str(ratio): _summary([row for row in rows if float(row["retention_ratio"]) == ratio])
            for ratio in ratios
        }
        methods[name]["by_geometry_type"] = {
            geometry_type: {
                **_summary(
                    [row for row in rows if str(row["geometry_type"]) == geometry_type]
                ),
                "by_retention_ratio": {
                    str(ratio): _summary(
                        [
                            row
                            for row in rows
                            if str(row["geometry_type"]) == geometry_type
                            and float(row["retention_ratio"]) == ratio
                        ]
                    )
                    for ratio in ratios
                },
            }
            for geometry_type in ("LineString", "Polygon")
            if any(str(row["geometry_type"]) == geometry_type for row in rows)
        }
    encoder_rows = measurements["encoder-remove-move"]
    paired_comparisons: dict[str, Any] = {}
    for baseline_name in (
        "teacher-consensus-oracle",
        "douglas-peucker",
        "visvalingam-whyatt",
    ):
        baseline_rows = measurements[baseline_name]
        paired_comparisons[baseline_name] = {
            **_paired_summary(encoder_rows, baseline_rows),
            "by_retention_ratio": {
                str(ratio): _paired_summary(
                    [row for row in encoder_rows if float(row["retention_ratio"]) == ratio],
                    [row for row in baseline_rows if float(row["retention_ratio"]) == ratio],
                )
                for ratio in ratios
            },
            "by_geometry_type": {
                geometry_type: _paired_summary(
                    [
                        row
                        for row in encoder_rows
                        if str(row["geometry_type"]) == geometry_type
                    ],
                    [
                        row
                        for row in baseline_rows
                        if str(row["geometry_type"]) == geometry_type
                    ],
                )
                for geometry_type in ("LineString", "Polygon")
                if any(str(row["geometry_type"]) == geometry_type for row in encoder_rows)
            },
        }
    teacher_rows = measurements["teacher-consensus-oracle"]
    teacher_comparisons: dict[str, Any] = {}
    for baseline_name in ("douglas-peucker", "visvalingam-whyatt"):
        baseline_rows = measurements[baseline_name]
        teacher_comparisons[baseline_name] = {
            **_renamed_pair_summary(
                teacher_rows,
                baseline_rows,
                candidate_name="teacher",
            ),
            "by_retention_ratio": {
                str(ratio): _renamed_pair_summary(
                    [row for row in teacher_rows if float(row["retention_ratio"]) == ratio],
                    [row for row in baseline_rows if float(row["retention_ratio"]) == ratio],
                    candidate_name="teacher",
                )
                for ratio in ratios
            },
            "by_geometry_type": {
                geometry_type: _renamed_pair_summary(
                    [
                        row
                        for row in teacher_rows
                        if str(row["geometry_type"]) == geometry_type
                    ],
                    [
                        row
                        for row in baseline_rows
                        if str(row["geometry_type"]) == geometry_type
                    ],
                    candidate_name="teacher",
                )
                for geometry_type in ("LineString", "Polygon")
                if any(str(row["geometry_type"]) == geometry_type for row in teacher_rows)
            },
        }
    return {
        "format_version": 1,
        "dataset_path": str(export_dir.resolve()),
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_metadata": metadata,
        "split": split,
        "split_fallback": split_fallback,
        "sample_count": len(samples),
        "budgets": list(ratios),
        "encoder_cold_start_latency_ms": encoder_cold_start_latency_ms,
        "encoder_fallback_rate": methods["encoder-remove-move"]["fallback_rate"],
        "teacher_oracle_note": (
            "Teacher latency measures reconstruction from precomputed labels and is not an "
            "inference benchmark."
        ),
        "methods": methods,
        "paired_comparisons": paired_comparisons,
        "teacher_comparisons": teacher_comparisons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a GeoScaleX encoder checkpoint")
    parser.add_argument("export_dir", type=Path, help="Published dataset version directory")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--split", default="test", choices=("train", "validation", "test"))
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--ratios", default="0.1,0.25,0.5,0.75")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    ratios = tuple(float(value.strip()) for value in arguments.ratios.split(",") if value.strip())
    report = evaluate(
        arguments.export_dir,
        arguments.checkpoint,
        split=arguments.split,
        device=arguments.device,
        ratios=ratios,
    )
    rendered = json.dumps(report, indent=2) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


def run() -> None:
    main()


if __name__ == "__main__":
    main()
