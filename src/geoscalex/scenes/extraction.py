from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

from pyproj import Transformer
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from shapely.strtree import STRtree
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from geoscalex.domain import (
    GeometryKind,
    SceneCreate,
    SceneExtractionCreate,
    SceneExtractionPreview,
    SceneExtractionProposal,
    SceneMemberCreate,
    SceneRole,
)
from geoscalex.storage import models

ENGINE_VERSION = "1"
SEMANTIC_KEYS = (
    "class",
    "type",
    "highway",
    "waterway",
    "railway",
    "natural",
    "boundary",
    "landuse",
)
ROLE_PRIORITY = {
    SceneRole.OBSTACLE: 0,
    SceneRole.PARENT: 1,
    SceneRole.CHILD: 1,
    SceneRole.SIBLING: 2,
    SceneRole.BACKGROUND: 3,
}
ROLE_Z_ORDER = {
    SceneRole.BACKGROUND: -20,
    SceneRole.PARENT: -10,
    SceneRole.SIBLING: 10,
    SceneRole.CHILD: 20,
    SceneRole.OBSTACLE: 30,
}


@dataclass(frozen=True)
class ExtractionFeature:
    id: str
    name: str
    batch_id: str | None
    revision_id: str
    revision_checksum: str
    geometry: BaseGeometry
    analysis_geometry: BaseGeometry
    geometry_type: GeometryKind
    coordinate_space: str
    crs: str | None
    properties: dict[str, Any]
    group_key: tuple[str, str | None]


@dataclass(frozen=True)
class PlannedScene:
    create: SceneCreate
    proposal: SceneExtractionProposal


@dataclass(frozen=True)
class ExtractionPlan:
    scenes: list[PlannedScene]
    eligible_targets: int
    isolated_targets: int
    existing_targets: int
    incompatible_features: int
    role_counts: dict[SceneRole, int]

    def preview(self, sample_size: int = 8) -> SceneExtractionPreview:
        return SceneExtractionPreview(
            eligible_targets=self.eligible_targets,
            proposed_scenes=len(self.scenes),
            isolated_targets=self.isolated_targets,
            existing_targets=self.existing_targets,
            incompatible_features=self.incompatible_features,
            role_counts=self.role_counts,
            samples=[item.proposal for item in self.scenes[:sample_size]],
        )


def _analysis_geometry(
    geometry: BaseGeometry, coordinate_space: str, crs: str | None
) -> BaseGeometry | None:
    if coordinate_space == "local":
        return geometry
    if not crs:
        return None
    try:
        transformer = Transformer.from_crs(crs, "EPSG:3857", always_xy=True)
        return transform(transformer.transform, geometry)
    except Exception:
        return None


def _semantic_signature(properties: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (key, str(properties[key]).casefold())
        for key in SEMANTIC_KEYS
        if properties.get(key) not in (None, "")
    }


def _relation(target: ExtractionFeature, context: ExtractionFeature) -> SceneRole:
    target_geometry = target.analysis_geometry
    context_geometry = context.analysis_geometry
    if context.geometry_type is GeometryKind.POLYGON and context_geometry.covers(target_geometry):
        return SceneRole.PARENT
    if target.geometry_type is GeometryKind.POLYGON and target_geometry.covers(context_geometry):
        return SceneRole.CHILD
    if target_geometry.intersects(context_geometry):
        return SceneRole.OBSTACLE
    if target.geometry_type is context.geometry_type:
        return SceneRole.SIBLING
    if _semantic_signature(target.properties) & _semantic_signature(context.properties):
        return SceneRole.SIBLING
    return SceneRole.BACKGROUND


def _viewport(features: list[ExtractionFeature]) -> dict[str, Any]:
    min_x = min(feature.geometry.bounds[0] for feature in features)
    min_y = min(feature.geometry.bounds[1] for feature in features)
    max_x = max(feature.geometry.bounds[2] for feature in features)
    max_y = max(feature.geometry.bounds[3] for feature in features)
    pad_x = max((max_x - min_x) * 0.05, 1e-9)
    pad_y = max((max_y - min_y) * 0.05, 1e-9)
    return {
        "mode": "extracted-scene",
        "bounds": [min_x - pad_x, min_y - pad_y, max_x + pad_x, max_y + pad_y],
    }


def _fingerprint(config: SceneExtractionCreate, target: ExtractionFeature) -> str:
    payload = {
        "engine_version": ENGINE_VERSION,
        "config": config.model_dump(mode="json", exclude={"max_scenes"}),
        "target_revision_checksum": target.revision_checksum,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _location_group(
    config: SceneExtractionCreate, target: ExtractionFeature
) -> str:
    centroid = target.analysis_geometry.centroid
    cell_size = max(config.radius * 2, 1e-9)
    cell_x = math.floor(centroid.x / cell_size)
    cell_y = math.floor(centroid.y / cell_size)
    return f"{config.location_group_prefix}:{target.group_key[0]}:{cell_x}:{cell_y}"


async def _load_features(
    session: AsyncSession, dataset_id: str
) -> tuple[list[ExtractionFeature], int]:
    records = (
        await session.scalars(
            select(models.Feature)
            .where(
                models.Feature.dataset_id == dataset_id,
                models.Feature.archived_at.is_(None),
            )
            .order_by(models.Feature.id)
        )
    ).all()
    revision_ids = [
        record.current_revision_id
        for record in records
        if record.current_revision_id is not None
    ]
    revisions = (
        await session.scalars(
            select(models.GeometryRevision).where(
                models.GeometryRevision.id.in_(revision_ids)
            )
        )
    ).all()
    revisions_by_id = {revision.id: revision for revision in revisions}
    features: list[ExtractionFeature] = []
    incompatible = 0
    for record in records:
        if record.current_revision_id is None:
            incompatible += 1
            continue
        revision = revisions_by_id.get(record.current_revision_id)
        if revision is None:
            incompatible += 1
            continue
        source_geometry = shape(revision.geometry_geojson)
        analysis_geometry = _analysis_geometry(
            source_geometry, revision.coordinate_space, revision.crs
        )
        try:
            geometry_type = GeometryKind(source_geometry.geom_type)
        except ValueError:
            incompatible += 1
            continue
        if analysis_geometry is None or analysis_geometry.is_empty:
            incompatible += 1
            continue
        features.append(
            ExtractionFeature(
                id=record.id,
                name=record.name,
                batch_id=record.batch_id,
                revision_id=revision.id,
                revision_checksum=revision.checksum,
                geometry=source_geometry,
                analysis_geometry=analysis_geometry,
                geometry_type=geometry_type,
                coordinate_space=revision.coordinate_space,
                crs=revision.crs,
                properties=revision.properties,
                group_key=(revision.coordinate_space, revision.crs),
            )
        )
    return features, incompatible


async def build_extraction_plan(
    session: AsyncSession, config: SceneExtractionCreate
) -> ExtractionPlan:
    dataset = await session.get(models.Dataset, str(config.dataset_id))
    if dataset is None:
        raise LookupError("Dataset not found")
    if config.target_batch_id is not None:
        batch = await session.get(models.Batch, str(config.target_batch_id))
        if batch is None or batch.dataset_id != str(config.dataset_id):
            raise ValueError("Target batch must belong to the extraction dataset")

    features, incompatible = await _load_features(session, str(config.dataset_id))
    existing_targets = set(
        (
            await session.scalars(
                select(models.Scene.target_feature_id).where(
                    models.Scene.dataset_id == str(config.dataset_id),
                    models.Scene.archived_at.is_(None),
                )
            )
        ).all()
    )
    target_types = set(config.geometry_types)
    targets = [
        feature
        for feature in features
        if feature.geometry_type in target_types
        and (
            config.target_batch_id is None
            or feature.batch_id == str(config.target_batch_id)
        )
    ]
    skipped_existing = 0
    if config.skip_existing_targets:
        skipped_existing = sum(target.id in existing_targets for target in targets)
        targets = [target for target in targets if target.id not in existing_targets]
    eligible_targets = min(len(targets), config.max_scenes)
    targets = targets[: config.max_scenes]

    grouped: dict[tuple[str, str | None], list[ExtractionFeature]] = {}
    for feature in features:
        grouped.setdefault(feature.group_key, []).append(feature)
    indexes = {
        key: STRtree([feature.analysis_geometry for feature in group])
        for key, group in grouped.items()
    }

    plans: list[PlannedScene] = []
    isolated = 0
    aggregate_roles: dict[SceneRole, int] = {role: 0 for role in SceneRole if role != "target"}
    for target in targets:
        group = grouped[target.group_key]
        tree = indexes[target.group_key]
        nearby_indices = tree.query(target.analysis_geometry.buffer(config.radius))
        ranked: list[tuple[int, float, str, ExtractionFeature, SceneRole]] = []
        for raw_index in nearby_indices:
            context = group[int(raw_index)]
            if context.id == target.id:
                continue
            distance = target.analysis_geometry.distance(context.analysis_geometry)
            if distance > config.radius:
                continue
            role = _relation(target, context)
            ranked.append((ROLE_PRIORITY[role], distance, context.id, context, role))
        ranked.sort(key=lambda item: (item[0], item[1], item[2]))
        selected = ranked[: config.max_context]
        if not selected:
            isolated += 1
            continue

        role_counts: dict[SceneRole, int] = {}
        members: list[SceneMemberCreate] = []
        for _, distance, _, context, role in selected:
            role_counts[role] = role_counts.get(role, 0) + 1
            aggregate_roles[role] += 1
            proximity = max(0.0, 1 - distance / config.radius)
            importance = min(
                1.0,
                0.25
                + 0.65 * proximity
                + (0.1 if role != SceneRole.BACKGROUND else 0),
            )
            members.append(
                SceneMemberCreate(
                    feature_id=context.id,
                    role=role,
                    importance=round(importance, 6),
                    z_order=ROLE_Z_ORDER[role],
                    style={
                        "extraction": {
                            "engine_version": ENGINE_VERSION,
                            "relation": role.value,
                            "distance": round(distance, 6),
                            "distance_unit": (
                                "metres"
                                if target.coordinate_space == "geographic"
                                else "coordinate-units"
                            ),
                        }
                    },
                )
            )
        viewport = _viewport([target, *[item[3] for item in selected]])
        location_group = _location_group(config, target)
        create = SceneCreate(
            dataset_id=config.dataset_id,
            name=f"Auto · {target.name}"[:200],
            target_feature_id=target.id,
            region=config.region,
            locality=config.locality,
            crs=target.crs,
            viewport=viewport,
            style={"preset": config.style_preset, "source": "scene-extraction"},
            scale_denominator=config.scale_denominator,
            provenance={
                "source": "automated-scene-extraction",
                "engine_version": ENGINE_VERSION,
                "fingerprint": _fingerprint(config, target),
                "target_revision_id": target.revision_id,
                "target_revision_checksum": target.revision_checksum,
                "location_group": location_group,
                "configuration": config.model_dump(mode="json"),
            },
            members=members,
        )
        proposal = SceneExtractionProposal(
            target_feature_id=target.id,
            target_name=target.name,
            context_count=len(members),
            roles=role_counts,
            viewport=viewport,
            location_group=location_group,
        )
        plans.append(PlannedScene(create=create, proposal=proposal))

    return ExtractionPlan(
        scenes=plans,
        eligible_targets=eligible_targets,
        isolated_targets=isolated,
        existing_targets=skipped_existing,
        incompatible_features=incompatible,
        role_counts=aggregate_roles,
    )
