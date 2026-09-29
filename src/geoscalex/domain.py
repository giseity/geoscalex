from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class CoordinateSpace(StrEnum):
    GEOGRAPHIC = "geographic"
    LOCAL = "local"


class GeometryKind(StrEnum):
    LINE_STRING = "LineString"
    POLYGON = "Polygon"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnnotationChoice(StrEnum):
    A = "A"
    B = "B"
    EQUAL = "equal"
    ARTIFACT = "artifact"


class SceneRegion(StrEnum):
    EUROPE = "europe"
    NORTH_AMERICA = "north-america"
    OTHER = "other"


class SceneRole(StrEnum):
    TARGET = "target"
    SIBLING = "sibling"
    PARENT = "parent"
    CHILD = "child"
    BACKGROUND = "background"
    OBSTACLE = "obstacle"


class Acceptability(StrEnum):
    ACCEPTABLE = "acceptable"
    UNACCEPTABLE = "unacceptable"
    UNSURE = "unsure"


class FailureTag(StrEnum):
    TOPOLOGY = "topology-failure"
    COLLISION = "visual-collision"
    DETAIL_LOSS = "excessive-detail-loss"
    SHAPE_LOSS = "characteristic-shape-loss"
    CONTEXT = "context-inconsistency"
    DISPLACEMENT = "displacement-needed"


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkspaceCreate(ApiModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceRead(WorkspaceCreate):
    id: UUID
    created_at: datetime


class DatasetCreate(ApiModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)


class DatasetRead(DatasetCreate):
    id: UUID
    created_at: datetime


class BatchCreate(ApiModel):
    dataset_id: UUID
    name: str = Field(min_length=1, max_length=160)
    source: str = Field(default="manual", max_length=80)
    provenance: dict[str, Any] = Field(default_factory=dict)


class BatchRead(BatchCreate):
    id: UUID
    created_at: datetime


class CollectionCreate(ApiModel):
    dataset_id: UUID
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)


class CollectionRead(CollectionCreate):
    id: UUID
    created_at: datetime


class FeatureCreate(ApiModel):
    dataset_id: UUID
    batch_id: UUID | None = None
    name: str = Field(default="Untitled feature", min_length=1, max_length=200)
    geometry: dict[str, Any]
    properties: dict[str, Any] = Field(default_factory=dict)
    coordinate_space: CoordinateSpace = CoordinateSpace.GEOGRAPHIC
    crs: str | None = "EPSG:4326"
    source: str = "manual"


class RevisionRead(ApiModel):
    id: UUID
    feature_id: UUID
    parent_revision_id: UUID | None
    sequence: int
    geometry: dict[str, Any]
    properties: dict[str, Any]
    coordinate_space: CoordinateSpace
    crs: str | None
    checksum: str
    change_kind: str
    created_at: datetime


class FeatureRead(ApiModel):
    id: UUID
    dataset_id: UUID
    batch_id: UUID | None
    name: str
    source: str
    archived_at: datetime | None
    current_revision: RevisionRead
    created_at: datetime


class RevisionCreate(ApiModel):
    geometry: dict[str, Any]
    properties: dict[str, Any] | None = None
    change_kind: str = Field(default="edit", max_length=40)


class DuplicateFeature(ApiModel):
    name: str | None = Field(default=None, max_length=200)


class CandidateRead(ApiModel):
    id: UUID
    revision_id: UUID
    method: str
    method_version: str
    parameters: dict[str, Any]
    geometry: dict[str, Any]
    vertex_scores: list[float | None]
    protected_mask: list[bool]
    metrics: dict[str, Any]
    created_at: datetime


class CandidateCreate(ApiModel):
    revision_id: UUID
    method: str
    tolerance: float | None = Field(default=None, ge=0)
    vertex_budget: int | None = Field(default=None, ge=2)


class HoleCreate(ApiModel):
    hole: dict[str, Any]


class GeoJsonImportCreate(ApiModel):
    dataset_id: UUID
    batch_name: str = Field(default="GeoJSON import", min_length=1, max_length=160)
    feature_collection: dict[str, Any]


class ImportResult(ApiModel):
    batch: BatchRead
    imported: int
    rejected: list[dict[str, Any]]
    feature_ids: list[UUID]


class DatasetPublishCreate(ApiModel):
    split_seed: int = 4812


class DatasetVersionRead(ApiModel):
    id: UUID
    dataset_id: UUID
    version: int
    manifest_path: str
    manifest_checksum: str
    split_seed: int
    created_at: datetime


class AnnotationCreate(ApiModel):
    dataset_id: UUID
    feature_id: UUID
    revision_id: UUID
    candidate_a_id: UUID | None = None
    candidate_b_id: UUID | None = None
    choice: AnnotationChoice
    viewport: dict[str, Any] = Field(default_factory=dict)
    comment: str = Field(default="", max_length=2000)


class AnnotationRead(AnnotationCreate):
    id: UUID
    created_at: datetime


class SceneMemberCreate(ApiModel):
    feature_id: UUID
    role: SceneRole = SceneRole.SIBLING
    importance: float = Field(default=0.5, ge=0, le=1)
    z_order: int = Field(default=0, ge=-1000, le=1000)
    style: dict[str, Any] = Field(default_factory=dict)


class SceneCreate(ApiModel):
    dataset_id: UUID
    name: str = Field(min_length=1, max_length=200)
    target_feature_id: UUID
    region: SceneRegion = SceneRegion.EUROPE
    locality: str = Field(default="", max_length=240)
    crs: str | None = Field(default="EPSG:4326", max_length=120)
    viewport: dict[str, Any] = Field(default_factory=dict)
    style: dict[str, Any] = Field(default_factory=dict)
    scale_denominator: float | None = Field(default=None, gt=0)
    zoom: float | None = Field(default=None, ge=0, le=30)
    provenance: dict[str, Any] = Field(default_factory=dict)
    members: list[SceneMemberCreate] = Field(default_factory=list, max_length=100)


class SceneMemberRead(SceneMemberCreate):
    feature: FeatureRead


class SceneRead(ApiModel):
    id: UUID
    dataset_id: UUID
    name: str
    target_feature_id: UUID
    region: SceneRegion
    locality: str
    crs: str | None
    viewport: dict[str, Any]
    style: dict[str, Any]
    scale_denominator: float | None
    zoom: float | None
    provenance: dict[str, Any]
    archived_at: datetime | None
    members: list[SceneMemberRead]
    created_at: datetime


class SceneReviewCreate(ApiModel):
    scene_id: UUID
    revision_id: UUID
    candidate_a_id: UUID | None = None
    candidate_b_id: UUID | None = None
    choice: AnnotationChoice
    acceptability: Acceptability = Acceptability.UNSURE
    failure_tags: list[FailureTag] = Field(default_factory=list)
    viewport: dict[str, Any] = Field(default_factory=dict)
    comment: str = Field(default="", max_length=2000)


class SceneReviewRead(SceneReviewCreate):
    id: UUID
    created_at: datetime


class JobRead(ApiModel):
    id: UUID
    kind: str
    status: JobStatus
    payload: dict[str, Any]
    progress: float
    logs: list[str]
    result: dict[str, Any]
    error: str | None
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class GeneratorRunCreate(ApiModel):
    dataset_id: UUID
    generator_id: str
    batch_name: str = Field(min_length=1, max_length=160)
    count: int = Field(default=10, ge=1, le=10000)
    seed: int = 4812
    parameters: dict[str, Any] = Field(default_factory=dict)


def new_id() -> str:
    return str(uuid4())
