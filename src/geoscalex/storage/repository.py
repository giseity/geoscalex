from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from shapely import from_wkb, to_wkb
from shapely.geometry import mapping, shape
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from geoscalex.domain import (
    AnnotationCreate,
    AnnotationRead,
    BatchCreate,
    BatchRead,
    CandidateCreate,
    CandidateRead,
    CollectionCreate,
    CollectionRead,
    DatasetCreate,
    DatasetRead,
    FeatureCreate,
    FeatureRead,
    GeneratorRunCreate,
    GeoJsonImportCreate,
    ImportResult,
    JobRead,
    RevisionCreate,
    RevisionRead,
    SceneCreate,
    SceneExtractionCreate,
    SceneMemberRead,
    SceneRead,
    SceneReviewCreate,
    SceneReviewRead,
    WorkspaceCreate,
    WorkspaceRead,
    utc_now,
)
from geoscalex.geometry.analysis import validate_geometry
from geoscalex.geometry.simplify import add_polygon_hole, build_candidate
from geoscalex.storage import models


def geometry_checksum(geometry: dict[str, Any], properties: dict[str, Any]) -> str:
    payload = json.dumps(
        {"geometry": geometry, "properties": properties}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode()).hexdigest()


async def require[ModelT: models.Record](
    session: AsyncSession, model: type[ModelT], record_id: UUID | str
) -> ModelT:
    record = await session.get(model, str(record_id))
    if record is None:
        raise LookupError(f"{model.__name__} not found")
    return record


async def create_workspace(session: AsyncSession, data: WorkspaceCreate) -> WorkspaceRead:
    record = models.Workspace(name=data.name)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return WorkspaceRead.model_validate(record)


async def list_workspaces(session: AsyncSession) -> list[WorkspaceRead]:
    records = (
        await session.scalars(select(models.Workspace).order_by(models.Workspace.created_at))
    ).all()
    return [WorkspaceRead.model_validate(record) for record in records]


async def create_dataset(session: AsyncSession, data: DatasetCreate) -> DatasetRead:
    await require(session, models.Workspace, data.workspace_id)
    record = models.Dataset(**data.model_dump(mode="json"))
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return DatasetRead.model_validate(record)


async def list_datasets(session: AsyncSession, workspace_id: UUID | None) -> list[DatasetRead]:
    statement: Select[tuple[models.Dataset]] = select(models.Dataset)
    if workspace_id:
        statement = statement.where(models.Dataset.workspace_id == str(workspace_id))
    records = (await session.scalars(statement.order_by(models.Dataset.created_at))).all()
    return [DatasetRead.model_validate(record) for record in records]


async def create_batch(session: AsyncSession, data: BatchCreate) -> BatchRead:
    await require(session, models.Dataset, data.dataset_id)
    record = models.Batch(**data.model_dump(mode="json"))
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return BatchRead.model_validate(record)


async def list_batches(session: AsyncSession, dataset_id: UUID) -> list[BatchRead]:
    records = (
        await session.scalars(
            select(models.Batch)
            .where(models.Batch.dataset_id == str(dataset_id))
            .order_by(models.Batch.created_at)
        )
    ).all()
    return [BatchRead.model_validate(record) for record in records]


async def create_collection(session: AsyncSession, data: CollectionCreate) -> CollectionRead:
    await require(session, models.Dataset, data.dataset_id)
    record = models.Collection(**data.model_dump(mode="json"))
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return CollectionRead.model_validate(record)


async def list_collections(session: AsyncSession, dataset_id: UUID) -> list[CollectionRead]:
    records = (
        await session.scalars(
            select(models.Collection)
            .where(models.Collection.dataset_id == str(dataset_id))
            .order_by(models.Collection.created_at)
        )
    ).all()
    return [CollectionRead.model_validate(record) for record in records]


def revision_read(record: models.GeometryRevision) -> RevisionRead:
    return RevisionRead(
        id=record.id,
        feature_id=record.feature_id,
        parent_revision_id=record.parent_revision_id,
        sequence=record.sequence,
        geometry=record.geometry_geojson,
        properties=record.properties,
        coordinate_space=record.coordinate_space,
        crs=record.crs,
        checksum=record.checksum,
        change_kind=record.change_kind,
        created_at=record.created_at,
    )


async def feature_read(session: AsyncSession, record: models.Feature) -> FeatureRead:
    if record.current_revision_id is None:
        raise RuntimeError("Feature has no current revision")
    revision = await require(session, models.GeometryRevision, record.current_revision_id)
    return FeatureRead(
        id=record.id,
        dataset_id=record.dataset_id,
        batch_id=record.batch_id,
        name=record.name,
        source=record.source,
        archived_at=record.archived_at,
        current_revision=revision_read(revision),
        created_at=record.created_at,
    )


async def create_feature(session: AsyncSession, data: FeatureCreate) -> FeatureRead:
    await require(session, models.Dataset, data.dataset_id)
    if data.batch_id:
        await require(session, models.Batch, data.batch_id)
    geometry = shape(validate_geometry(data.geometry).geometry)
    feature = models.Feature(
        dataset_id=str(data.dataset_id),
        batch_id=str(data.batch_id) if data.batch_id else None,
        name=data.name,
        source=data.source,
    )
    session.add(feature)
    await session.flush()
    normalized_geojson = mapping(geometry)
    revision = models.GeometryRevision(
        feature_id=feature.id,
        parent_revision_id=None,
        sequence=1,
        geometry_wkb=to_wkb(geometry),
        geometry_geojson=normalized_geojson,
        properties=data.properties,
        coordinate_space=data.coordinate_space.value,
        crs=data.crs,
        checksum=geometry_checksum(normalized_geojson, data.properties),
        change_kind="create",
    )
    session.add(revision)
    await session.flush()
    feature.current_revision_id = revision.id
    await session.commit()
    await session.refresh(feature)
    return await feature_read(session, feature)


async def list_features(
    session: AsyncSession, dataset_id: UUID, include_archived: bool = False
) -> list[FeatureRead]:
    statement = select(models.Feature).where(models.Feature.dataset_id == str(dataset_id))
    if not include_archived:
        statement = statement.where(models.Feature.archived_at.is_(None))
    records = (await session.scalars(statement.order_by(models.Feature.created_at))).all()
    return [await feature_read(session, record) for record in records]


async def get_feature(session: AsyncSession, feature_id: UUID) -> FeatureRead:
    return await feature_read(session, await require(session, models.Feature, feature_id))


async def list_revisions(session: AsyncSession, feature_id: UUID) -> list[RevisionRead]:
    await require(session, models.Feature, feature_id)
    records = (
        await session.scalars(
            select(models.GeometryRevision)
            .where(models.GeometryRevision.feature_id == str(feature_id))
            .order_by(models.GeometryRevision.sequence.desc())
        )
    ).all()
    return [revision_read(record) for record in records]


async def add_revision(
    session: AsyncSession, feature_id: UUID, data: RevisionCreate
) -> FeatureRead:
    feature = await require(session, models.Feature, feature_id)
    if feature.current_revision_id is None:
        raise RuntimeError("Feature has no current revision")
    parent = await require(session, models.GeometryRevision, feature.current_revision_id)
    geometry = shape(validate_geometry(data.geometry).geometry)
    geojson = mapping(geometry)
    properties = data.properties if data.properties is not None else parent.properties
    revision = models.GeometryRevision(
        feature_id=feature.id,
        parent_revision_id=parent.id,
        sequence=parent.sequence + 1,
        geometry_wkb=to_wkb(geometry),
        geometry_geojson=geojson,
        properties=properties,
        coordinate_space=parent.coordinate_space,
        crs=parent.crs,
        checksum=geometry_checksum(geojson, properties),
        change_kind=data.change_kind,
    )
    session.add(revision)
    await session.flush()
    feature.current_revision_id = revision.id
    await session.commit()
    await session.refresh(feature)
    return await feature_read(session, feature)


async def restore_revision(
    session: AsyncSession, feature_id: UUID, revision_id: UUID
) -> FeatureRead:
    feature = await require(session, models.Feature, feature_id)
    revision = await require(session, models.GeometryRevision, revision_id)
    if revision.feature_id != feature.id:
        raise ValueError("Revision does not belong to this feature")
    return await add_revision(
        session,
        feature_id,
        RevisionCreate(
            geometry=revision.geometry_geojson,
            properties=revision.properties,
            change_kind=f"restore-r{revision.sequence}",
        ),
    )


async def add_hole(session: AsyncSession, feature_id: UUID, hole: dict[str, Any]) -> FeatureRead:
    feature = await require(session, models.Feature, feature_id)
    if feature.current_revision_id is None:
        raise RuntimeError("Feature has no current revision")
    revision = await require(session, models.GeometryRevision, feature.current_revision_id)
    geometry = add_polygon_hole(revision.geometry_geojson, hole)
    return await add_revision(
        session,
        feature_id,
        RevisionCreate(geometry=geometry, change_kind="add-hole"),
    )


async def duplicate_feature(
    session: AsyncSession, feature_id: UUID, name: str | None
) -> FeatureRead:
    source = await require(session, models.Feature, feature_id)
    if source.current_revision_id is None:
        raise RuntimeError("Feature has no current revision")
    revision = await require(session, models.GeometryRevision, source.current_revision_id)
    geometry = mapping(from_wkb(revision.geometry_wkb))
    return await create_feature(
        session,
        FeatureCreate(
            dataset_id=UUID(source.dataset_id),
            batch_id=UUID(source.batch_id) if source.batch_id else None,
            name=name or f"{source.name} copy",
            geometry=geometry,
            properties={**revision.properties, "duplicated_from": source.id},
            coordinate_space=revision.coordinate_space,
            crs=revision.crs,
            source="duplicate",
        ),
    )


async def set_archived(session: AsyncSession, feature_id: UUID, archived: bool) -> FeatureRead:
    feature = await require(session, models.Feature, feature_id)
    feature.archived_at = utc_now() if archived else None
    await session.commit()
    await session.refresh(feature)
    return await feature_read(session, feature)


async def add_to_collection(session: AsyncSession, collection_id: UUID, feature_id: UUID) -> None:
    await require(session, models.Collection, collection_id)
    await require(session, models.Feature, feature_id)
    existing = await session.get(
        models.CollectionFeature,
        {"collection_id": str(collection_id), "feature_id": str(feature_id)},
    )
    if existing is None:
        session.add(
            models.CollectionFeature(collection_id=str(collection_id), feature_id=str(feature_id))
        )
        await session.commit()


async def create_annotation(session: AsyncSession, data: AnnotationCreate) -> AnnotationRead:
    await require(session, models.Dataset, data.dataset_id)
    feature = await require(session, models.Feature, data.feature_id)
    revision = await require(session, models.GeometryRevision, data.revision_id)
    if feature.dataset_id != str(data.dataset_id) or revision.feature_id != feature.id:
        raise ValueError("Annotation feature, revision, and dataset do not match")
    for candidate_id in (data.candidate_a_id, data.candidate_b_id):
        if candidate_id is None:
            continue
        candidate = await require(session, models.Candidate, candidate_id)
        if candidate.revision_id != revision.id:
            raise ValueError("Annotation candidates must belong to the annotated revision")
    record = models.ComparisonAnnotation(**data.model_dump(mode="json"))
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return AnnotationRead.model_validate(record)


async def scene_read(session: AsyncSession, record: models.Scene) -> SceneRead:
    memberships = (
        await session.scalars(
            select(models.SceneFeature)
            .where(models.SceneFeature.scene_id == record.id)
            .order_by(models.SceneFeature.z_order, models.SceneFeature.feature_id)
        )
    ).all()
    members = [
        SceneMemberRead(
            feature_id=membership.feature_id,
            role=membership.role,
            importance=membership.importance,
            z_order=membership.z_order,
            style=membership.style,
            feature=await feature_read(
                session, await require(session, models.Feature, membership.feature_id)
            ),
        )
        for membership in memberships
    ]
    return SceneRead(
        id=record.id,
        dataset_id=record.dataset_id,
        name=record.name,
        target_feature_id=record.target_feature_id,
        region=record.region,
        locality=record.locality,
        crs=record.crs,
        viewport=record.viewport,
        style=record.style,
        scale_denominator=record.scale_denominator,
        zoom=record.zoom,
        provenance=record.provenance,
        archived_at=record.archived_at,
        members=members,
        created_at=record.created_at,
    )


async def create_scene(session: AsyncSession, data: SceneCreate) -> SceneRead:
    await require(session, models.Dataset, data.dataset_id)
    target = await require(session, models.Feature, data.target_feature_id)
    if target.dataset_id != str(data.dataset_id):
        raise ValueError("Scene target must belong to the scene dataset")
    if target.archived_at is not None:
        raise ValueError("Archived features cannot be scene targets")

    member_ids = [str(member.feature_id) for member in data.members]
    if str(data.target_feature_id) in member_ids:
        raise ValueError("The target is added automatically and must not be repeated")
    if len(member_ids) != len(set(member_ids)):
        raise ValueError("A feature can only appear once in a scene")
    if any(member.role.value == "target" for member in data.members):
        raise ValueError("Only the scene target can have the target role")

    context_features: dict[str, models.Feature] = {}
    for member in data.members:
        feature = await require(session, models.Feature, member.feature_id)
        if feature.dataset_id != str(data.dataset_id):
            raise ValueError("Every scene member must belong to the scene dataset")
        if feature.archived_at is not None:
            raise ValueError("Archived features cannot be added to scenes")
        context_features[feature.id] = feature

    record = models.Scene(
        dataset_id=str(data.dataset_id),
        name=data.name,
        target_feature_id=str(data.target_feature_id),
        region=data.region.value,
        locality=data.locality,
        crs=data.crs,
        viewport=data.viewport,
        style=data.style,
        scale_denominator=data.scale_denominator,
        zoom=data.zoom,
        provenance=data.provenance,
    )
    session.add(record)
    await session.flush()
    session.add(
        models.SceneFeature(
            scene_id=record.id,
            feature_id=target.id,
            role="target",
            importance=1.0,
            z_order=100,
            style={},
        )
    )
    for member in data.members:
        session.add(
            models.SceneFeature(
                scene_id=record.id,
                feature_id=context_features[str(member.feature_id)].id,
                role=member.role.value,
                importance=member.importance,
                z_order=member.z_order,
                style=member.style,
            )
        )
    await session.commit()
    await session.refresh(record)
    return await scene_read(session, record)


async def list_scenes(
    session: AsyncSession, dataset_id: UUID, include_archived: bool = False
) -> list[SceneRead]:
    await require(session, models.Dataset, dataset_id)
    statement = select(models.Scene).where(models.Scene.dataset_id == str(dataset_id))
    if not include_archived:
        statement = statement.where(models.Scene.archived_at.is_(None))
    records = (await session.scalars(statement.order_by(models.Scene.created_at))).all()
    return [await scene_read(session, record) for record in records]


async def get_scene(session: AsyncSession, scene_id: UUID) -> SceneRead:
    return await scene_read(session, await require(session, models.Scene, scene_id))


async def set_scene_archived(
    session: AsyncSession, scene_id: UUID, archived: bool
) -> SceneRead:
    scene = await require(session, models.Scene, scene_id)
    scene.archived_at = utc_now() if archived else None
    await session.commit()
    await session.refresh(scene)
    return await scene_read(session, scene)


async def create_scene_review(
    session: AsyncSession, data: SceneReviewCreate
) -> SceneReviewRead:
    scene = await require(session, models.Scene, data.scene_id)
    revision = await require(session, models.GeometryRevision, data.revision_id)
    if revision.feature_id != scene.target_feature_id:
        raise ValueError("Scene reviews must use a revision of the target feature")
    for candidate_id in (data.candidate_a_id, data.candidate_b_id):
        if candidate_id is None:
            continue
        candidate = await require(session, models.Candidate, candidate_id)
        if candidate.revision_id != revision.id:
            raise ValueError("Scene review candidates must belong to the target revision")
    record = models.SceneReview(**data.model_dump(mode="json"))
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return SceneReviewRead.model_validate(record)


async def list_scene_reviews(
    session: AsyncSession, scene_id: UUID
) -> list[SceneReviewRead]:
    await require(session, models.Scene, scene_id)
    records = (
        await session.scalars(
            select(models.SceneReview)
            .where(models.SceneReview.scene_id == str(scene_id))
            .order_by(models.SceneReview.created_at.desc())
        )
    ).all()
    return [SceneReviewRead.model_validate(record) for record in records]


def candidate_read(record: models.Candidate) -> CandidateRead:
    return CandidateRead(
        id=record.id,
        revision_id=record.revision_id,
        method=record.method,
        method_version=record.method_version,
        parameters=record.parameters,
        geometry=record.geometry_geojson,
        vertex_scores=record.vertex_scores,
        protected_mask=record.protected_mask,
        metrics=record.metrics,
        created_at=record.created_at,
    )


async def create_candidate(session: AsyncSession, data: CandidateCreate) -> CandidateRead:
    revision = await require(session, models.GeometryRevision, data.revision_id)
    candidate, hierarchy, metrics = build_candidate(
        revision.geometry_geojson,
        data.method,
        tolerance=data.tolerance,
        budget=data.vertex_budget,
    )
    scores = [None if value == float("inf") else value for value in hierarchy.scores]
    record = models.Candidate(
        revision_id=revision.id,
        method=data.method,
        method_version="1",
        parameters={"tolerance": data.tolerance, "vertex_budget": data.vertex_budget},
        geometry_geojson=candidate,
        vertex_scores=scores,
        protected_mask=hierarchy.protected,
        metrics=metrics,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return candidate_read(record)


async def list_candidates(session: AsyncSession, revision_id: UUID) -> list[CandidateRead]:
    records = (
        await session.scalars(
            select(models.Candidate)
            .where(models.Candidate.revision_id == str(revision_id))
            .order_by(models.Candidate.created_at)
        )
    ).all()
    return [candidate_read(record) for record in records]


async def next_dataset_version(session: AsyncSession, dataset_id: UUID) -> int:
    current = await session.scalar(
        select(func.max(models.DatasetVersion.version)).where(
            models.DatasetVersion.dataset_id == str(dataset_id)
        )
    )
    return (current or 0) + 1


def job_read(record: models.Job) -> JobRead:
    return JobRead.model_validate(record)


async def enqueue_generator_run(
    session: AsyncSession, data: GeneratorRunCreate, code_hash: str, version: str
) -> JobRead:
    await require(session, models.Dataset, data.dataset_id)
    job = models.Job(
        kind="generator-run",
        payload={
            **data.model_dump(mode="json"),
            "generator_version": version,
            "code_hash": code_hash,
        },
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job_read(job)


async def enqueue_scene_extraction(
    session: AsyncSession, data: SceneExtractionCreate
) -> JobRead:
    await require(session, models.Dataset, data.dataset_id)
    if data.target_batch_id is not None:
        batch = await require(session, models.Batch, data.target_batch_id)
        if batch.dataset_id != str(data.dataset_id):
            raise ValueError("Target batch must belong to the extraction dataset")
    job = models.Job(
        kind="scene-extraction",
        payload=data.model_dump(mode="json"),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job_read(job)


async def list_jobs(session: AsyncSession, limit: int = 100) -> list[JobRead]:
    records = (
        await session.scalars(
            select(models.Job).order_by(models.Job.created_at.desc()).limit(limit)
        )
    ).all()
    return [job_read(record) for record in records]


async def get_job(session: AsyncSession, job_id: UUID) -> JobRead:
    return job_read(await require(session, models.Job, job_id))


async def request_job_cancel(session: AsyncSession, job_id: UUID) -> JobRead:
    job = await require(session, models.Job, job_id)
    if job.status in {"queued", "running"}:
        job.cancel_requested = True
        job.logs = [*job.logs, "Cancellation requested"]
        await session.commit()
        await session.refresh(job)
    return job_read(job)


async def import_geojson(session: AsyncSession, data: GeoJsonImportCreate) -> ImportResult:
    collection = data.feature_collection
    if collection.get("type") != "FeatureCollection" or not isinstance(
        collection.get("features"), list
    ):
        raise ValueError("Expected a GeoJSON FeatureCollection")
    batch = await create_batch(
        session,
        BatchCreate(
            dataset_id=data.dataset_id,
            name=data.batch_name,
            source="geojson",
            provenance={"feature_count": len(collection["features"])},
        ),
    )
    imported: list[UUID] = []
    rejected: list[dict[str, Any]] = []
    for index, item in enumerate(collection["features"]):
        try:
            if item.get("type") != "Feature" or not isinstance(item.get("geometry"), dict):
                raise ValueError("Expected a GeoJSON Feature")
            properties = item.get("properties") or {}
            feature = await create_feature(
                session,
                FeatureCreate(
                    dataset_id=data.dataset_id,
                    batch_id=batch.id,
                    name=str(properties.get("name") or f"Imported feature {index + 1}"),
                    geometry=item["geometry"],
                    properties=properties,
                    coordinate_space="geographic",
                    crs="EPSG:4326",
                    source="geojson",
                ),
            )
            imported.append(feature.id)
        except Exception as error:
            rejected.append({"index": index, "reason": str(error)})
    return ImportResult(
        batch=batch, imported=len(imported), rejected=rejected, feature_ids=imported
    )
