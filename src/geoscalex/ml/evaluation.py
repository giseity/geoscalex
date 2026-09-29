from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any

from geoscalex.geometry.analysis import comparison_metrics, validate_geometry
from geoscalex.geometry.simplify import build_candidate
from geoscalex.ml.data import load_samples
from geoscalex.ml.inference import infer_geometry, load_checkpoint


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def evaluate(
    export_dir: Path,
    checkpoint: Path,
    *,
    split: str = "test",
    device: str = "cpu",
) -> dict[str, Any]:
    samples = load_samples(export_dir, split=split)
    split_fallback = False
    if not samples and split == "test":
        samples = load_samples(export_dir, split="validation")
        split = "validation"
        split_fallback = True
    if not samples:
        raise ValueError(f"No {split} samples found in {export_dir}")
    model, metadata = load_checkpoint(checkpoint, device)
    measurements: dict[str, list[dict[str, Any]]] = {
        "encoder-remove-move": [],
        "douglas-peucker": [],
        "visvalingam-whyatt": [],
    }
    fallback_count = 0
    for sample in samples:
        source_analysis = validate_geometry(sample.geometry)
        source_count = source_analysis.vertex_count
        min_x, min_y, max_x, max_y = source_analysis.bounds
        diagonal = max(math.hypot(max_x - min_x, max_y - min_y), 1e-9)
        minimum = 3 if sample.geometry["type"] == "Polygon" else 2
        for ratio in (0.25, 0.5):
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
            measurements["encoder-remove-move"].append(encoder_metrics)
            fallback_count += int(bool(diagnostics["fallback_used"]))
            for method in ("douglas-peucker", "visvalingam-whyatt"):
                started = time.perf_counter()
                classical, _, _ = build_candidate(sample.geometry, method, budget=budget)
                metrics = comparison_metrics(sample.geometry, classical)
                metrics["normalized_hausdorff_distance"] = metrics["hausdorff_distance"] / diagonal
                metrics["latency_ms"] = (time.perf_counter() - started) * 1000
                metrics["budget_satisfied"] = metrics["vertex_count"] == budget
                measurements[method].append(metrics)

    methods: dict[str, Any] = {}
    for name, rows in measurements.items():
        methods[name] = {
            "candidate_count": len(rows),
            "validity_rate": _mean([float(row["is_valid"]) for row in rows]),
            "budget_satisfaction_rate": _mean([float(row["budget_satisfied"]) for row in rows]),
            "mean_hausdorff_distance": _mean([float(row["hausdorff_distance"]) for row in rows]),
            "mean_normalized_hausdorff_distance": _mean(
                [float(row["normalized_hausdorff_distance"]) for row in rows]
            ),
            "mean_frechet_distance": _mean([float(row["frechet_distance"]) for row in rows]),
            "mean_latency_ms": _mean([float(row["latency_ms"]) for row in rows]),
        }
    encoder_count = len(measurements["encoder-remove-move"])
    return {
        "format_version": 1,
        "dataset_path": str(export_dir.resolve()),
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_metadata": metadata,
        "split": split,
        "split_fallback": split_fallback,
        "sample_count": len(samples),
        "budgets": [0.25, 0.5],
        "encoder_fallback_rate": fallback_count / encoder_count if encoder_count else 0.0,
        "methods": methods,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a GeoScaleX encoder checkpoint")
    parser.add_argument("export_dir", type=Path, help="Published dataset version directory")
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--split", default="test", choices=("train", "validation", "test"))
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = evaluate(
        arguments.export_dir,
        arguments.checkpoint,
        split=arguments.split,
        device=arguments.device,
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
