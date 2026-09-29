from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from geoscalex.api.dependencies import DatabaseSession
from geoscalex.config import settings
from geoscalex.datasets.io import list_versions, publish_dataset
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
    DatasetPublishCreate,
    DatasetRead,
    DatasetVersionRead,
    DuplicateFeature,
    FeatureCreate,
    FeatureRead,
    GeneratorRunCreate,
    GeoJsonImportCreate,
    HoleCreate,
    ImportResult,
    JobRead,
    RevisionCreate,
    RevisionRead,
    SceneCreate,
    SceneExtractionCreate,
    SceneExtractionPreview,
    SceneRead,
    SceneReviewCreate,
    SceneReviewRead,
    SimplificationMethodRead,
    SimplificationRunCreate,
    WorkspaceCreate,
    WorkspaceRead,
)
from geoscalex.generators import generator_registry
from geoscalex.generators.registry import GeneratorDefinition
from geoscalex.geometry.analysis import GeometryValidationError
from geoscalex.scenes.extraction import build_extraction_plan
from geoscalex.simplification import method_registry
from geoscalex.simplification.gateway import gateway_available
from geoscalex.storage import repository

router = APIRouter()


def not_found(error: LookupError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(error))


@router.post("/workspaces", response_model=WorkspaceRead, status_code=201)
async def create_workspace(data: WorkspaceCreate, session: DatabaseSession) -> WorkspaceRead:
    return await repository.create_workspace(session, data)


@router.get("/workspaces", response_model=list[WorkspaceRead])
async def workspaces(session: DatabaseSession) -> list[WorkspaceRead]:
    return await repository.list_workspaces(session)


@router.post("/datasets", response_model=DatasetRead, status_code=201)
async def create_dataset(data: DatasetCreate, session: DatabaseSession) -> DatasetRead:
    try:
        return await repository.create_dataset(session, data)
    except LookupError as error:
        raise not_found(error) from error


@router.get("/datasets", response_model=list[DatasetRead])
async def datasets(session: DatabaseSession, workspace_id: UUID | None = None) -> list[DatasetRead]:
    return await repository.list_datasets(session, workspace_id)


@router.post("/batches", response_model=BatchRead, status_code=201)
async def create_batch(data: BatchCreate, session: DatabaseSession) -> BatchRead:
    try:
        return await repository.create_batch(session, data)
    except LookupError as error:
        raise not_found(error) from error


@router.get("/datasets/{dataset_id}/batches", response_model=list[BatchRead])
async def batches(dataset_id: UUID, session: DatabaseSession) -> list[BatchRead]:
    return await repository.list_batches(session, dataset_id)


@router.post("/collections", response_model=CollectionRead, status_code=201)
async def create_collection(data: CollectionCreate, session: DatabaseSession) -> CollectionRead:
    try:
        return await repository.create_collection(session, data)
    except LookupError as error:
        raise not_found(error) from error


@router.get("/datasets/{dataset_id}/collections", response_model=list[CollectionRead])
async def collections(dataset_id: UUID, session: DatabaseSession) -> list[CollectionRead]:
    return await repository.list_collections(session, dataset_id)


@router.put("/collections/{collection_id}/features/{feature_id}", status_code=204)
async def add_collection_feature(
    collection_id: UUID, feature_id: UUID, session: DatabaseSession
) -> Response:
    try:
        await repository.add_to_collection(session, collection_id, feature_id)
    except LookupError as error:
        raise not_found(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/features", response_model=FeatureRead, status_code=201)
async def create_feature(data: FeatureCreate, session: DatabaseSession) -> FeatureRead:
    try:
        return await repository.create_feature(session, data)
    except LookupError as error:
        raise not_found(error) from error
    except GeometryValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/datasets/{dataset_id}/features", response_model=list[FeatureRead])
async def features(
    dataset_id: UUID, session: DatabaseSession, include_archived: bool = False
) -> list[FeatureRead]:
    return await repository.list_features(session, dataset_id, include_archived)


@router.get("/features/{feature_id}", response_model=FeatureRead)
async def feature(feature_id: UUID, session: DatabaseSession) -> FeatureRead:
    try:
        return await repository.get_feature(session, feature_id)
    except LookupError as error:
        raise not_found(error) from error
    except GeometryValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/features/{feature_id}/revisions", response_model=list[RevisionRead])
async def revisions(feature_id: UUID, session: DatabaseSession) -> list[RevisionRead]:
    try:
        return await repository.list_revisions(session, feature_id)
    except LookupError as error:
        raise not_found(error) from error


@router.post("/features/{feature_id}/revisions", response_model=FeatureRead, status_code=201)
async def create_revision(
    feature_id: UUID, data: RevisionCreate, session: DatabaseSession
) -> FeatureRead:
    try:
        return await repository.add_revision(session, feature_id, data)
    except LookupError as error:
        raise not_found(error) from error


@router.post(
    "/features/{feature_id}/revisions/{revision_id}/restore",
    response_model=FeatureRead,
    status_code=201,
)
async def restore_revision(
    feature_id: UUID, revision_id: UUID, session: DatabaseSession
) -> FeatureRead:
    try:
        return await repository.restore_revision(session, feature_id, revision_id)
    except LookupError as error:
        raise not_found(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/features/{feature_id}/duplicate", response_model=FeatureRead, status_code=201)
async def duplicate_feature(
    feature_id: UUID, data: DuplicateFeature, session: DatabaseSession
) -> FeatureRead:
    try:
        return await repository.duplicate_feature(session, feature_id, data.name)
    except LookupError as error:
        raise not_found(error) from error


@router.post("/features/{feature_id}/archive", response_model=FeatureRead)
async def archive_feature(feature_id: UUID, session: DatabaseSession) -> FeatureRead:
    try:
        return await repository.set_archived(session, feature_id, True)
    except LookupError as error:
        raise not_found(error) from error


@router.post("/features/{feature_id}/restore", response_model=FeatureRead)
async def restore_feature(feature_id: UUID, session: DatabaseSession) -> FeatureRead:
    try:
        return await repository.set_archived(session, feature_id, False)
    except LookupError as error:
        raise not_found(error) from error


@router.post("/annotations", response_model=AnnotationRead, status_code=201)
async def create_annotation(data: AnnotationCreate, session: DatabaseSession) -> AnnotationRead:
    try:
        return await repository.create_annotation(session, data)
    except LookupError as error:
        raise not_found(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/scenes", response_model=SceneRead, status_code=201)
async def create_scene(data: SceneCreate, session: DatabaseSession) -> SceneRead:
    try:
        return await repository.create_scene(session, data)
    except LookupError as error:
        raise not_found(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/datasets/{dataset_id}/scenes", response_model=list[SceneRead])
async def scenes(
    dataset_id: UUID, session: DatabaseSession, include_archived: bool = False
) -> list[SceneRead]:
    try:
        return await repository.list_scenes(session, dataset_id, include_archived)
    except LookupError as error:
        raise not_found(error) from error


@router.get("/scenes/{scene_id}", response_model=SceneRead)
async def scene(scene_id: UUID, session: DatabaseSession) -> SceneRead:
    try:
        return await repository.get_scene(session, scene_id)
    except LookupError as error:
        raise not_found(error) from error


@router.post("/scenes/{scene_id}/archive", response_model=SceneRead)
async def archive_scene(scene_id: UUID, session: DatabaseSession) -> SceneRead:
    try:
        return await repository.set_scene_archived(session, scene_id, True)
    except LookupError as error:
        raise not_found(error) from error


@router.post("/scene-reviews", response_model=SceneReviewRead, status_code=201)
async def create_scene_review(data: SceneReviewCreate, session: DatabaseSession) -> SceneReviewRead:
    try:
        return await repository.create_scene_review(session, data)
    except LookupError as error:
        raise not_found(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/scene-extractions/preview", response_model=SceneExtractionPreview)
async def preview_scene_extraction(
    data: SceneExtractionCreate, session: DatabaseSession
) -> SceneExtractionPreview:
    try:
        return (await build_extraction_plan(session, data)).preview()
    except LookupError as error:
        raise not_found(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/scene-extractions", response_model=JobRead, status_code=202)
async def create_scene_extraction(data: SceneExtractionCreate, session: DatabaseSession) -> JobRead:
    try:
        return await repository.enqueue_scene_extraction(session, data)
    except LookupError as error:
        raise not_found(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/scenes/{scene_id}/reviews", response_model=list[SceneReviewRead])
async def scene_reviews(scene_id: UUID, session: DatabaseSession) -> list[SceneReviewRead]:
    try:
        return await repository.list_scene_reviews(session, scene_id)
    except LookupError as error:
        raise not_found(error) from error


@router.post("/candidates", response_model=CandidateRead, status_code=201)
async def create_candidate(data: CandidateCreate, session: DatabaseSession) -> CandidateRead:
    try:
        return await repository.create_candidate(session, data)
    except LookupError as error:
        raise not_found(error) from error
    except (GeometryValidationError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/features/{feature_id}/holes", response_model=FeatureRead, status_code=201)
async def create_hole(feature_id: UUID, data: HoleCreate, session: DatabaseSession) -> FeatureRead:
    try:
        return await repository.add_hole(session, feature_id, data.hole)
    except LookupError as error:
        raise not_found(error) from error
    except GeometryValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/revisions/{revision_id}/candidates", response_model=list[CandidateRead])
async def candidates(revision_id: UUID, session: DatabaseSession) -> list[CandidateRead]:
    return await repository.list_candidates(session, revision_id)


@router.get("/simplification-methods", response_model=list[SimplificationMethodRead])
async def simplification_methods() -> list[SimplificationMethodRead]:
    return method_registry.definitions(
        deepseek_available=await gateway_available(),
        encoder_available=bool(
            settings.encoder_checkpoint and settings.encoder_checkpoint.exists()
        ),
    )


@router.post("/simplification-runs", response_model=JobRead, status_code=202)
async def create_simplification_run(
    data: SimplificationRunCreate, session: DatabaseSession
) -> JobRead:
    try:
        available = {method.id: method for method in await simplification_methods()}
        method = available.get(data.method)
        if method is None:
            raise LookupError(f"Unknown simplification method: {data.method}")
        if not method.available:
            raise ValueError(method.unavailable_reason or f"{method.name} is unavailable")
        return await repository.enqueue_simplification_run(session, data)
    except LookupError as error:
        raise not_found(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/generators", response_model=list[GeneratorDefinition])
async def generators() -> list[GeneratorDefinition]:
    return generator_registry.definitions()


@router.post("/generator-runs", response_model=JobRead, status_code=202)
async def create_generator_run(data: GeneratorRunCreate, session: DatabaseSession) -> JobRead:
    try:
        entry = generator_registry.get(data.generator_id)
        entry.parameters.model_validate(data.parameters)
        return await repository.enqueue_generator_run(
            session, data, entry.definition.code_hash, entry.definition.version
        )
    except LookupError as error:
        raise not_found(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/jobs", response_model=list[JobRead])
async def jobs(session: DatabaseSession, limit: int = 100) -> list[JobRead]:
    return await repository.list_jobs(session, min(limit, 500))


@router.get("/jobs/{job_id}", response_model=JobRead)
async def job(job_id: UUID, session: DatabaseSession) -> JobRead:
    try:
        return await repository.get_job(session, job_id)
    except LookupError as error:
        raise not_found(error) from error


@router.post("/jobs/{job_id}/cancel", response_model=JobRead)
async def cancel_job(job_id: UUID, session: DatabaseSession) -> JobRead:
    try:
        return await repository.request_job_cancel(session, job_id)
    except LookupError as error:
        raise not_found(error) from error


@router.post("/imports/geojson", response_model=ImportResult, status_code=201)
async def import_geojson(data: GeoJsonImportCreate, session: DatabaseSession) -> ImportResult:
    try:
        return await repository.import_geojson(session, data)
    except (GeometryValidationError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/datasets/{dataset_id}/versions", response_model=DatasetVersionRead, status_code=201)
async def publish(
    dataset_id: UUID, data: DatasetPublishCreate, session: DatabaseSession
) -> DatasetVersionRead:
    try:
        return await publish_dataset(session, dataset_id, data.split_seed)
    except LookupError as error:
        raise not_found(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/datasets/{dataset_id}/versions", response_model=list[DatasetVersionRead])
async def versions(dataset_id: UUID, session: DatabaseSession) -> list[DatasetVersionRead]:
    return await list_versions(session, dataset_id)
