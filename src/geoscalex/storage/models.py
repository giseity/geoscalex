from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from geoscalex.domain import new_id, utc_now


class Base(DeclarativeBase):
    pass


class Record(Base):
    __abstract__ = True
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Workspace(Record):
    __tablename__ = "workspaces"
    name: Mapped[str] = mapped_column(String(120))


class Dataset(Record):
    __tablename__ = "datasets"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")


class Batch(Record):
    __tablename__ = "batches"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(String(80), default="manual")
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Collection(Record):
    __tablename__ = "collections"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")


class CollectionFeature(Base):
    __tablename__ = "collection_features"
    collection_id: Mapped[str] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    feature_id: Mapped[str] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"), primary_key=True
    )


class Feature(Record):
    __tablename__ = "features"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    batch_id: Mapped[str | None] = mapped_column(ForeignKey("batches.id", ondelete="SET NULL"))
    current_revision_id: Mapped[str | None] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(80), default="manual")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GeometryRevision(Record):
    __tablename__ = "geometry_revisions"
    feature_id: Mapped[str] = mapped_column(ForeignKey("features.id", ondelete="CASCADE"))
    parent_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("geometry_revisions.id", ondelete="SET NULL")
    )
    sequence: Mapped[int] = mapped_column(Integer)
    geometry_wkb: Mapped[bytes] = mapped_column(LargeBinary)
    geometry_geojson: Mapped[dict[str, Any]] = mapped_column(JSON)
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    coordinate_space: Mapped[str] = mapped_column(String(24))
    crs: Mapped[str | None] = mapped_column(String(120))
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    change_kind: Mapped[str] = mapped_column(String(40), default="edit")


class Candidate(Record):
    __tablename__ = "candidates"
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("geometry_revisions.id", ondelete="CASCADE")
    )
    method: Mapped[str] = mapped_column(String(60))
    method_version: Mapped[str] = mapped_column(String(32), default="1")
    method_kind: Mapped[str] = mapped_column(String(32), default="classical")
    job_id: Mapped[str | None] = mapped_column(String(36), index=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    requested_budget: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    resolved_vertex_budget: Mapped[int | None] = mapped_column(Integer, index=True)
    geometry_geojson: Mapped[dict[str, Any]] = mapped_column(JSON)
    vertex_scores: Mapped[list[float | None]] = mapped_column(JSON, default=list)
    protected_mask: Mapped[list[bool]] = mapped_column(JSON, default=list)
    source_mapping: Mapped[list[int]] = mapped_column(JSON, default=list)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    diagnostics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ComparisonAnnotation(Record):
    __tablename__ = "comparison_annotations"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    feature_id: Mapped[str] = mapped_column(ForeignKey("features.id", ondelete="CASCADE"))
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("geometry_revisions.id", ondelete="CASCADE")
    )
    candidate_a_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"))
    candidate_b_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"))
    choice: Mapped[str] = mapped_column(String(16))
    viewport: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    comment: Mapped[str] = mapped_column(Text, default="")


class Scene(Record):
    __tablename__ = "scenes"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    target_feature_id: Mapped[str] = mapped_column(ForeignKey("features.id", ondelete="CASCADE"))
    region: Mapped[str] = mapped_column(String(32))
    locality: Mapped[str] = mapped_column(String(240), default="")
    crs: Mapped[str | None] = mapped_column(String(120))
    viewport: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    style: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scale_denominator: Mapped[float | None] = mapped_column(Float)
    zoom: Mapped[float | None] = mapped_column(Float)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SceneFeature(Base):
    __tablename__ = "scene_features"
    scene_id: Mapped[str] = mapped_column(
        ForeignKey("scenes.id", ondelete="CASCADE"), primary_key=True
    )
    feature_id: Mapped[str] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(24))
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    z_order: Mapped[int] = mapped_column(Integer, default=0)
    style: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SceneReview(Record):
    __tablename__ = "scene_reviews"
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.id", ondelete="CASCADE"))
    revision_id: Mapped[str] = mapped_column(
        ForeignKey("geometry_revisions.id", ondelete="CASCADE")
    )
    candidate_a_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"))
    candidate_b_id: Mapped[str | None] = mapped_column(ForeignKey("candidates.id"))
    choice: Mapped[str] = mapped_column(String(16))
    acceptability: Mapped[str] = mapped_column(String(20), default="unsure")
    failure_tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    viewport: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    comment: Mapped[str] = mapped_column(Text, default="")


class DatasetVersion(Record):
    __tablename__ = "dataset_versions"
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    manifest_path: Mapped[str] = mapped_column(Text)
    manifest_checksum: Mapped[str] = mapped_column(String(64))
    split_seed: Mapped[int] = mapped_column(Integer, default=4812)


class DatasetVersionItem(Base):
    __tablename__ = "dataset_version_items"
    dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="CASCADE"), primary_key=True
    )
    feature_id: Mapped[str] = mapped_column(ForeignKey("features.id"), primary_key=True)
    revision_id: Mapped[str] = mapped_column(ForeignKey("geometry_revisions.id"))
    split: Mapped[str] = mapped_column(String(12))


class DatasetVersionScene(Base):
    __tablename__ = "dataset_version_scenes"
    dataset_version_id: Mapped[str] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="CASCADE"), primary_key=True
    )
    scene_id: Mapped[str] = mapped_column(ForeignKey("scenes.id"), primary_key=True)
    target_revision_id: Mapped[str] = mapped_column(ForeignKey("geometry_revisions.id"))
    split: Mapped[str] = mapped_column(String(12))


class Job(Record):
    __tablename__ = "jobs"
    kind: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    logs: Mapped[list[str]] = mapped_column(JSON, default=list)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
