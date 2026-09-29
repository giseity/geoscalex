from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from shapely import to_wkb
from shapely.geometry import shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from geoscalex.config import settings
from geoscalex.domain import DatasetVersionRead
from geoscalex.geometry.analysis import analyze_geometry
from geoscalex.geometry.simplify import hierarchy_scores
from geoscalex.storage import models, repository


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _split(group: str, seed: int) -> str:
    digest = hashlib.sha256(f"{seed}:{group}".encode()).digest()
    value = int.from_bytes(digest[:8], "big") / 2**64
    if value < 0.8:
        return "train"
    if value < 0.9:
        return "validation"
    return "test"


async def publish_dataset(
    session: AsyncSession, dataset_id: UUID, split_seed: int
) -> DatasetVersionRead:
    dataset = await repository.require(session, models.Dataset, dataset_id)
    features = (
        await session.scalars(
            select(models.Feature)
            .where(models.Feature.dataset_id == str(dataset_id))
            .where(models.Feature.archived_at.is_(None))
            .order_by(models.Feature.id)
        )
    ).all()
    if not features:
        raise ValueError("Cannot publish an empty dataset")

    version_number = await repository.next_dataset_version(session, dataset_id)
    export_dir = settings.data_dir / "exports" / str(dataset_id) / f"v{version_number}"
    export_dir.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    version_items: list[tuple[models.Feature, models.GeometryRevision, str]] = []
    revision_ids: list[str] = []
    for feature in features:
        if feature.current_revision_id is None:
            continue
        revision = await repository.require(
            session, models.GeometryRevision, feature.current_revision_id
        )
        dp = hierarchy_scores(revision.geometry_geojson, "douglas-peucker")
        vw = hierarchy_scores(revision.geometry_geojson, "visvalingam-whyatt")
        metrics = analyze_geometry(revision.geometry_geojson)
        split_group = feature.batch_id or feature.id
        split = _split(split_group, split_seed)
        rows.append(
            {
                "feature_id": feature.id,
                "revision_id": revision.id,
                "batch_id": feature.batch_id,
                "name": feature.name,
                "source": feature.source,
                "geometry_type": revision.geometry_geojson["type"],
                "geometry_wkb": to_wkb(shape(revision.geometry_geojson)),
                "properties_json": json.dumps(revision.properties, sort_keys=True),
                "coordinate_space": revision.coordinate_space,
                "crs": revision.crs,
                "checksum": revision.checksum,
                "split_group": split_group,
                "split": split,
                "vertex_count": metrics["vertex_count"],
                "dp_scores": [None if value == float("inf") else value for value in dp.scores],
                "dp_protected": dp.protected,
                "vw_scores": [None if value == float("inf") else value for value in vw.scores],
                "vw_protected": vw.protected,
            }
        )
        version_items.append((feature, revision, split))
        revision_ids.append(revision.id)

    parquet_path = export_dir / "features.parquet"
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, parquet_path, compression="zstd", row_group_size=10_000)

    candidates = (
        await session.scalars(
            select(models.Candidate)
            .where(models.Candidate.revision_id.in_(revision_ids))
            .order_by(models.Candidate.id)
        )
    ).all()
    candidate_rows = [
        {
            "candidate_id": candidate.id,
            "revision_id": candidate.revision_id,
            "method": candidate.method,
            "method_version": candidate.method_version,
            "parameters_json": json.dumps(candidate.parameters, sort_keys=True),
            "geometry_wkb": to_wkb(shape(candidate.geometry_geojson)),
            "metrics_json": json.dumps(candidate.metrics, sort_keys=True),
        }
        for candidate in candidates
    ]
    candidate_schema = pa.schema(
        [
            ("candidate_id", pa.string()),
            ("revision_id", pa.string()),
            ("method", pa.string()),
            ("method_version", pa.string()),
            ("parameters_json", pa.string()),
            ("geometry_wkb", pa.binary()),
            ("metrics_json", pa.string()),
        ]
    )
    candidates_path = export_dir / "candidates.parquet"
    pq.write_table(
        pa.Table.from_pylist(candidate_rows, schema=candidate_schema),
        candidates_path,
        compression="zstd",
    )

    annotations = (
        await session.scalars(
            select(models.ComparisonAnnotation)
            .where(models.ComparisonAnnotation.dataset_id == str(dataset_id))
            .where(models.ComparisonAnnotation.revision_id.in_(revision_ids))
            .order_by(models.ComparisonAnnotation.id)
        )
    ).all()
    annotation_rows = [
        {
            "annotation_id": annotation.id,
            "feature_id": annotation.feature_id,
            "revision_id": annotation.revision_id,
            "candidate_a_id": annotation.candidate_a_id,
            "candidate_b_id": annotation.candidate_b_id,
            "choice": annotation.choice,
            "viewport_json": json.dumps(annotation.viewport, sort_keys=True),
            "comment": annotation.comment,
        }
        for annotation in annotations
    ]
    annotation_schema = pa.schema(
        [
            ("annotation_id", pa.string()),
            ("feature_id", pa.string()),
            ("revision_id", pa.string()),
            ("candidate_a_id", pa.string()),
            ("candidate_b_id", pa.string()),
            ("choice", pa.string()),
            ("viewport_json", pa.string()),
            ("comment", pa.string()),
        ]
    )
    annotations_path = export_dir / "annotations.parquet"
    pq.write_table(
        pa.Table.from_pylist(annotation_rows, schema=annotation_schema),
        annotations_path,
        compression="zstd",
    )

    with duckdb.connect() as connection:
        result = connection.execute(
            "SELECT count(*) FROM read_parquet(?)", [str(parquet_path)]
        ).fetchone()
        if result is None:
            raise RuntimeError("DuckDB export verification returned no result")
        count = result[0]
    if count != len(rows):
        raise RuntimeError("DuckDB export verification failed")

    export_files = [parquet_path, candidates_path, annotations_path]
    manifest = {
        "format": "geoscalex-dataset",
        "schema_version": 1,
        "dataset_id": str(dataset_id),
        "dataset_name": dataset.name,
        "version": version_number,
        "split_seed": split_seed,
        "feature_count": len(rows),
        "candidate_count": len(candidate_rows),
        "annotation_count": len(annotation_rows),
        "files": [{"path": path.name, "sha256": _checksum(path)} for path in export_files],
    }
    manifest_path = export_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    manifest_checksum = _checksum(manifest_path)

    version = models.DatasetVersion(
        dataset_id=str(dataset_id),
        version=version_number,
        manifest_path=str(manifest_path),
        manifest_checksum=manifest_checksum,
        split_seed=split_seed,
    )
    session.add(version)
    await session.flush()
    for feature, revision, split in version_items:
        session.add(
            models.DatasetVersionItem(
                dataset_version_id=version.id,
                feature_id=feature.id,
                revision_id=revision.id,
                split=split,
            )
        )
    await session.commit()
    await session.refresh(version)
    return DatasetVersionRead.model_validate(version)


async def list_versions(session: AsyncSession, dataset_id: UUID) -> list[DatasetVersionRead]:
    records = (
        await session.scalars(
            select(models.DatasetVersion)
            .where(models.DatasetVersion.dataset_id == str(dataset_id))
            .order_by(models.DatasetVersion.version.desc())
        )
    ).all()
    return [DatasetVersionRead.model_validate(record) for record in records]
