from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
from shapely import from_wkb
from shapely.geometry import mapping

from geoscalex.geometry.analysis import GeometryValidationError, validate_geometry


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read(path: Path) -> list[dict[str, Any]]:
    return pq.read_table(path).to_pylist() if path.exists() else []


def _distribution(values: list[int]) -> dict[str, int | float]:
    if not values:
        return {
            "count": 0,
            "total": 0,
            "min": 0,
            "p25": 0,
            "median": 0,
            "p75": 0,
            "p95": 0,
            "max": 0,
        }
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": len(values),
        "total": int(array.sum()),
        "min": int(array.min()),
        "p25": float(np.quantile(array, 0.25)),
        "median": float(np.quantile(array, 0.5)),
        "p75": float(np.quantile(array, 0.75)),
        "p95": float(np.quantile(array, 0.95)),
        "max": int(array.max()),
    }


def _nested_counts(rows: list[dict[str, Any]], outer: str, inner: str) -> dict[str, Any]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        counts[str(row[outer])][str(row[inner])] += 1
    return {key: dict(sorted(value.items())) for key, value in sorted(counts.items())}


def audit_export(export_dir: Path, *, model_vertex_limit: int = 512) -> dict[str, Any]:
    export_dir = export_dir.resolve()
    fatal: list[str] = []
    warnings: list[str] = []
    manifest_path = export_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"Dataset manifest does not exist: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "geoscalex-dataset":
        fatal.append("Manifest format is not geoscalex-dataset")

    checked_files: list[dict[str, Any]] = []
    for declared in manifest.get("files", []):
        relative = Path(str(declared.get("path", "")))
        if not relative.name or relative.is_absolute() or len(relative.parts) != 1:
            fatal.append(f"Unsafe manifest path: {relative}")
            continue
        path = export_dir / relative
        if not path.exists():
            fatal.append(f"Manifest file is missing: {relative}")
            continue
        actual = _checksum(path)
        matches = actual == declared.get("sha256")
        if not matches:
            fatal.append(f"Checksum mismatch: {relative}")
        checked_files.append({"path": str(relative), "sha256": actual, "matches": matches})

    features_path = export_dir / "features.parquet"
    if not features_path.exists():
        fatal.append("features.parquet is missing")
        features: list[dict[str, Any]] = []
    else:
        features = _read(features_path)
    if int(manifest.get("feature_count", -1)) != len(features):
        fatal.append(
            f"Manifest feature_count={manifest.get('feature_count')} but features.parquet has "
            f"{len(features)} rows"
        )

    split_counts: Counter[str] = Counter()
    geometry_counts: Counter[str] = Counter()
    generator_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    coordinate_space_counts: Counter[str] = Counter()
    vertex_counts: list[int] = []
    split_groups: dict[str, set[str]] = defaultdict(set)
    geometry_hash_splits: dict[str, set[str]] = defaultdict(set)
    geometry_hash_rows: Counter[str] = Counter()
    teacher_failures = 0
    invalid_geometries = 0
    model_eligible = 0
    normalized_rows: list[dict[str, Any]] = []

    for row_number, row in enumerate(features, start=1):
        split = str(row.get("split", "missing"))
        split_group = str(row.get("split_group", "missing"))
        split_counts[split] += 1
        split_groups[split_group].add(split)
        source_counts[str(row.get("source") or "unknown")] += 1
        coordinate_space_counts[str(row.get("coordinate_space") or "unknown")] += 1
        properties: dict[str, Any]
        try:
            properties = json.loads(row.get("properties_json") or "{}")
        except json.JSONDecodeError:
            properties = {}
            fatal.append(f"Feature row {row_number} has invalid properties_json")
        generator = str(properties.get("generator_id") or row.get("source") or "unknown")
        generator_counts[generator] += 1
        normalized_rows.append(
            {"split": split, "geometry_type": str(row.get("geometry_type")), "generator": generator}
        )

        geometry_wkb = row.get("geometry_wkb")
        if not isinstance(geometry_wkb, bytes):
            invalid_geometries += 1
            fatal.append(f"Feature row {row_number} has no binary geometry_wkb")
            continue
        geometry_hash = hashlib.sha256(geometry_wkb).hexdigest()
        geometry_hash_rows[geometry_hash] += 1
        geometry_hash_splits[geometry_hash].add(split)
        try:
            geometry = mapping(from_wkb(geometry_wkb))
            analysis = validate_geometry(geometry)
        except (GeometryValidationError, TypeError, ValueError) as error:
            invalid_geometries += 1
            fatal.append(f"Feature row {row_number} is invalid: {error}")
            continue
        geometry_counts[analysis.geometry_type] += 1
        vertex_counts.append(analysis.vertex_count)
        if analysis.vertex_count <= model_vertex_limit and (
            analysis.geometry_type == "LineString" or analysis.ring_count == 1
        ):
            model_eligible += 1

        expected_scores = analysis.coordinate_count
        for field in ("dp_scores", "vw_scores"):
            scores = row.get(field)
            if not isinstance(scores, list) or len(scores) != expected_scores:
                teacher_failures += 1
                fatal.append(
                    f"Feature row {row_number} {field} has "
                    f"{len(scores) if isinstance(scores, list) else 'no'} values; "
                    f"expected {expected_scores}"
                )
                continue
            if any(
                score is not None
                and (not isinstance(score, (int, float)) or not math.isfinite(float(score)))
                for score in scores
            ):
                teacher_failures += 1
                fatal.append(f"Feature row {row_number} {field} contains a non-finite value")

    leaking_groups = sorted(group for group, splits in split_groups.items() if len(splits) > 1)
    if leaking_groups:
        fatal.append(f"{len(leaking_groups)} split groups appear in more than one split")
    cross_split_duplicates = sorted(
        checksum for checksum, splits in geometry_hash_splits.items() if len(splits) > 1
    )
    if cross_split_duplicates:
        fatal.append(f"{len(cross_split_duplicates)} duplicate geometries cross split boundaries")
    duplicate_rows = sum(count - 1 for count in geometry_hash_rows.values() if count > 1)
    if duplicate_rows:
        warnings.append(f"{duplicate_rows} duplicate geometry rows exist within the export")

    for split in ("train", "validation", "test"):
        if not split_counts[split]:
            warnings.append(f"No features are assigned to the {split} split")
    for geometry_type in ("LineString", "Polygon"):
        present = {row["split"] for row in normalized_rows if row["geometry_type"] == geometry_type}
        missing = sorted({"train", "validation", "test"} - present)
        if missing:
            warnings.append(f"{geometry_type} is absent from splits: {', '.join(missing)}")
    for generator in generator_counts:
        present = {row["split"] for row in normalized_rows if row["generator"] == generator}
        missing = sorted({"train", "validation", "test"} - present)
        if missing:
            warnings.append(
                f"Generator family {generator} is absent from splits: {', '.join(missing)}"
            )
    if features and model_eligible / len(features) < 0.9:
        warnings.append("Fewer than 90% of features are eligible for the initial encoder")

    candidates = _read(export_dir / "candidates.parquet")
    reviews = _read(export_dir / "scene_reviews.parquet")
    candidates_by_id = {str(row["candidate_id"]): row for row in candidates}
    accepted_ids: set[str] = set()
    for review in reviews:
        if review.get("acceptability") != "acceptable":
            continue
        if review.get("choice") == "A" and review.get("candidate_a_id"):
            accepted_ids.add(str(review["candidate_a_id"]))
        elif review.get("choice") == "B" and review.get("candidate_b_id"):
            accepted_ids.add(str(review["candidate_b_id"]))
        elif review.get("choice") == "equal":
            accepted_ids.update(
                str(candidate_id)
                for candidate_id in (review.get("candidate_a_id"), review.get("candidate_b_id"))
                if candidate_id
            )
    movement_candidates = sum(
        bool(candidates_by_id[candidate_id].get("source_mapping"))
        for candidate_id in accepted_ids
        if candidate_id in candidates_by_id
    )
    if not movement_candidates:
        warnings.append("No acceptable reviewed candidate can supervise vertex movement")

    return {
        "audit_version": 1,
        "ok": not fatal,
        "export_dir": str(export_dir),
        "manifest": {
            "schema_version": manifest.get("schema_version"),
            "dataset_id": manifest.get("dataset_id"),
            "version": manifest.get("version"),
            "files": checked_files,
        },
        "fatal": fatal,
        "warnings": warnings,
        "features": {
            "count": len(features),
            "geometry_types": dict(sorted(geometry_counts.items())),
            "splits": dict(sorted(split_counts.items())),
            "split_by_geometry_type": _nested_counts(normalized_rows, "split", "geometry_type"),
            "generator_families": dict(sorted(generator_counts.items())),
            "split_by_generator": _nested_counts(normalized_rows, "split", "generator"),
            "sources": dict(sorted(source_counts.items())),
            "coordinate_spaces": dict(sorted(coordinate_space_counts.items())),
            "vertices": _distribution(vertex_counts),
            "model_eligible": model_eligible,
            "model_vertex_limit": model_vertex_limit,
            "invalid": invalid_geometries,
            "teacher_failures": teacher_failures,
            "duplicate_rows": duplicate_rows,
            "cross_split_duplicates": len(cross_split_duplicates),
            "leaking_split_groups": len(leaking_groups),
        },
        "supervision": {
            "candidate_count": len(candidates),
            "scene_review_count": len(reviews),
            "acceptable_candidate_count": len(accepted_ids),
            "movement_candidate_count": movement_candidates,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a published GeoScaleX dataset version")
    parser.add_argument("export_dir", type=Path)
    parser.add_argument("--model-vertex-limit", type=int, default=512)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = audit_export(arguments.export_dir, model_vertex_limit=arguments.model_vertex_limit)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not report["ok"]:
        raise SystemExit(1)


def run() -> None:
    main()


if __name__ == "__main__":
    main()
