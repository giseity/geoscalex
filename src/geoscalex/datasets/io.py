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


def assign_split(group: str, seed: int) -> str:
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
    active_revisions: dict[str, models.GeometryRevision] = {}
    active_features = {feature.id: feature for feature in features}
    for feature in features:
        if feature.current_revision_id is None:
            continue
        revision = await repository.require(
            session, models.GeometryRevision, feature.current_revision_id
        )
        dp = hierarchy_scores(revision.geometry_geojson, "douglas-peucker")
        vw = hierarchy_scores(revision.geometry_geojson, "visvalingam-whyatt")
        metrics = analyze_geometry(revision.geometry_geojson)
        split_group = str(revision.properties.get("split_group") or feature.batch_id or feature.id)
        split = assign_split(split_group, split_seed)
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
        active_revisions[feature.id] = revision

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
            "method_kind": candidate.method_kind,
            "job_id": candidate.job_id,
            "parameters_json": json.dumps(candidate.parameters, sort_keys=True),
            "requested_budget_json": json.dumps(candidate.requested_budget, sort_keys=True),
            "resolved_vertex_budget": candidate.resolved_vertex_budget,
            "geometry_wkb": to_wkb(shape(candidate.geometry_geojson)),
            "source_mapping": candidate.source_mapping,
            "provenance_json": json.dumps(candidate.provenance, sort_keys=True),
            "diagnostics_json": json.dumps(candidate.diagnostics, sort_keys=True),
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
            ("method_kind", pa.string()),
            ("job_id", pa.string()),
            ("parameters_json", pa.string()),
            ("requested_budget_json", pa.string()),
            ("resolved_vertex_budget", pa.int64()),
            ("geometry_wkb", pa.binary()),
            ("source_mapping", pa.list_(pa.int64())),
            ("provenance_json", pa.string()),
            ("diagnostics_json", pa.string()),
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

    scenes = (
        await session.scalars(
            select(models.Scene)
            .where(models.Scene.dataset_id == str(dataset_id))
            .where(models.Scene.archived_at.is_(None))
            .order_by(models.Scene.id)
        )
    ).all()
    scene_rows: list[dict[str, Any]] = []
    scene_member_rows: list[dict[str, Any]] = []
    version_scenes: list[tuple[models.Scene, models.GeometryRevision, str]] = []
    current_scene_revisions: dict[str, str] = {}
    for scene in scenes:
        target = active_features.get(scene.target_feature_id)
        scene_target_revision = active_revisions.get(scene.target_feature_id)
        if target is None or scene_target_revision is None:
            raise ValueError(f"Scene {scene.name!r} has an archived target")
        split_group = str(scene.provenance.get("location_group") or target.batch_id or scene.id)
        split = assign_split(split_group, split_seed)
        scene_rows.append(
            {
                "scene_id": scene.id,
                "name": scene.name,
                "target_feature_id": scene.target_feature_id,
                "target_revision_id": scene_target_revision.id,
                "region": scene.region,
                "locality": scene.locality,
                "crs": scene.crs,
                "viewport_json": json.dumps(scene.viewport, sort_keys=True),
                "style_json": json.dumps(scene.style, sort_keys=True),
                "scale_denominator": scene.scale_denominator,
                "zoom": scene.zoom,
                "provenance_json": json.dumps(scene.provenance, sort_keys=True),
                "split_group": split_group,
                "split": split,
            }
        )
        version_scenes.append((scene, scene_target_revision, split))
        current_scene_revisions[scene.id] = scene_target_revision.id
        memberships = (
            await session.scalars(
                select(models.SceneFeature)
                .where(models.SceneFeature.scene_id == scene.id)
                .order_by(models.SceneFeature.z_order, models.SceneFeature.feature_id)
            )
        ).all()
        for membership in memberships:
            member_revision = active_revisions.get(membership.feature_id)
            if member_revision is None:
                raise ValueError(f"Scene {scene.name!r} contains an archived member")
            scene_member_rows.append(
                {
                    "scene_id": scene.id,
                    "feature_id": membership.feature_id,
                    "revision_id": member_revision.id,
                    "role": membership.role,
                    "importance": membership.importance,
                    "z_order": membership.z_order,
                    "style_json": json.dumps(membership.style, sort_keys=True),
                }
            )

    scene_schema = pa.schema(
        [
            ("scene_id", pa.string()),
            ("name", pa.string()),
            ("target_feature_id", pa.string()),
            ("target_revision_id", pa.string()),
            ("region", pa.string()),
            ("locality", pa.string()),
            ("crs", pa.string()),
            ("viewport_json", pa.string()),
            ("style_json", pa.string()),
            ("scale_denominator", pa.float64()),
            ("zoom", pa.float64()),
            ("provenance_json", pa.string()),
            ("split_group", pa.string()),
            ("split", pa.string()),
        ]
    )
    scenes_path = export_dir / "scenes.parquet"
    pq.write_table(
        pa.Table.from_pylist(scene_rows, schema=scene_schema), scenes_path, compression="zstd"
    )

    scene_member_schema = pa.schema(
        [
            ("scene_id", pa.string()),
            ("feature_id", pa.string()),
            ("revision_id", pa.string()),
            ("role", pa.string()),
            ("importance", pa.float64()),
            ("z_order", pa.int64()),
            ("style_json", pa.string()),
        ]
    )
    scene_members_path = export_dir / "scene_members.parquet"
    pq.write_table(
        pa.Table.from_pylist(scene_member_rows, schema=scene_member_schema),
        scene_members_path,
        compression="zstd",
    )

    scene_reviews = (
        await session.scalars(
            select(models.SceneReview)
            .where(models.SceneReview.scene_id.in_(list(current_scene_revisions)))
            .order_by(models.SceneReview.id)
        )
    ).all()
    scene_review_rows = [
        {
            "review_id": review.id,
            "scene_id": review.scene_id,
            "revision_id": review.revision_id,
            "candidate_a_id": review.candidate_a_id,
            "candidate_b_id": review.candidate_b_id,
            "choice": review.choice,
            "acceptability": review.acceptability,
            "failure_tags": review.failure_tags,
            "viewport_json": json.dumps(review.viewport, sort_keys=True),
            "comment": review.comment,
        }
        for review in scene_reviews
        if current_scene_revisions.get(review.scene_id) == review.revision_id
    ]
    scene_review_schema = pa.schema(
        [
            ("review_id", pa.string()),
            ("scene_id", pa.string()),
            ("revision_id", pa.string()),
            ("candidate_a_id", pa.string()),
            ("candidate_b_id", pa.string()),
            ("choice", pa.string()),
            ("acceptability", pa.string()),
            ("failure_tags", pa.list_(pa.string())),
            ("viewport_json", pa.string()),
            ("comment", pa.string()),
        ]
    )
    scene_reviews_path = export_dir / "scene_reviews.parquet"
    pq.write_table(
        pa.Table.from_pylist(scene_review_rows, schema=scene_review_schema),
        scene_reviews_path,
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

    export_files = [
        parquet_path,
        candidates_path,
        annotations_path,
        scenes_path,
        scene_members_path,
        scene_reviews_path,
    ]
    manifest = {
        "format": "geoscalex-dataset",
        "schema_version": 3,
        "dataset_id": str(dataset_id),
        "dataset_name": dataset.name,
        "version": version_number,
        "split_seed": split_seed,
        "feature_count": len(rows),
        "candidate_count": len(candidate_rows),
        "annotation_count": len(annotation_rows),
        "scene_count": len(scene_rows),
        "scene_member_count": len(scene_member_rows),
        "scene_review_count": len(scene_review_rows),
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
    for scene, revision, split in version_scenes:
        session.add(
            models.DatasetVersionScene(
                dataset_version_id=version.id,
                scene_id=scene.id,
                target_revision_id=revision.id,
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
