from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from geoscalex.domain import (
    BatchCreate,
    DatasetCreate,
    FeatureCreate,
    SceneExtractionCreate,
    SceneRole,
    WorkspaceCreate,
)
from geoscalex.scenes.extraction import ENGINE_VERSION, build_extraction_plan
from geoscalex.storage.models import Base
from geoscalex.storage.repository import (
    create_batch,
    create_dataset,
    create_feature,
    create_scene,
    create_workspace,
    enqueue_scene_extraction,
)


@pytest.mark.asyncio
async def test_extraction_plans_explainable_spatial_roles(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        workspace = await create_workspace(session, WorkspaceCreate(name="Research"))
        dataset = await create_dataset(
            session, DatasetCreate(workspace_id=workspace.id, name="Spatial corpus")
        )
        target_batch = await create_batch(
            session,
            BatchCreate(dataset_id=dataset.id, name="Targets", source="test"),
        )
        target = await create_feature(
            session,
            FeatureCreate(
                dataset_id=dataset.id,
                batch_id=target_batch.id,
                name="Target river",
                geometry={"type": "LineString", "coordinates": [[0, 0], [10, 0]]},
                properties={"waterway": "river"},
                coordinate_space="local",
                crs=None,
            ),
        )
        context_specs = [
            (
                "Basin",
                {
                    "type": "Polygon",
                    "coordinates": [[[-1, -1], [11, -1], [11, 1], [-1, 1], [-1, -1]]],
                },
                {},
            ),
            (
                "Crossing rail",
                {"type": "LineString", "coordinates": [[5, -3], [5, 3]]},
                {"railway": "rail"},
            ),
            (
                "Parallel stream",
                {"type": "LineString", "coordinates": [[0, 3], [10, 3]]},
                {"waterway": "river"},
            ),
            (
                "Nearby land",
                {
                    "type": "Polygon",
                    "coordinates": [[[2, 4], [4, 4], [4, 6], [2, 6], [2, 4]]],
                },
                {"landuse": "forest"},
            ),
        ]
        for name, geometry, properties in context_specs:
            await create_feature(
                session,
                FeatureCreate(
                    dataset_id=dataset.id,
                    name=name,
                    geometry=geometry,
                    properties=properties,
                    coordinate_space="local",
                    crs=None,
                ),
            )

        config = SceneExtractionCreate(
            dataset_id=dataset.id,
            target_batch_id=target_batch.id,
            radius=10,
            max_context=10,
            locality="Test basin",
            location_group_prefix="basin",
        )
        plan = await build_extraction_plan(session, config)
        preview = plan.preview()

        assert preview.eligible_targets == 1
        assert preview.proposed_scenes == 1
        assert preview.isolated_targets == 0
        assert preview.role_counts[SceneRole.PARENT] == 1
        assert preview.role_counts[SceneRole.OBSTACLE] == 1
        assert preview.role_counts[SceneRole.SIBLING] == 1
        assert preview.role_counts[SceneRole.BACKGROUND] == 1
        assert preview.samples[0].target_feature_id == target.id

        planned = plan.scenes[0]
        scene = await create_scene(session, planned.create)
        member_roles = {member.feature.name: member.role for member in scene.members}
        assert member_roles["Basin"] is SceneRole.PARENT
        assert member_roles["Crossing rail"] is SceneRole.OBSTACLE
        assert member_roles["Parallel stream"] is SceneRole.SIBLING
        assert member_roles["Nearby land"] is SceneRole.BACKGROUND
        assert scene.provenance["engine_version"] == ENGINE_VERSION
        assert len(scene.provenance["fingerprint"]) == 64

        repeated = await build_extraction_plan(session, config)
        assert repeated.existing_targets == 1
        assert repeated.scenes == []

        queued = await enqueue_scene_extraction(
            session, config.model_copy(update={"skip_existing_targets": False})
        )
        assert queued.kind == "scene-extraction"
        assert queued.payload["radius"] == 10.0

    await engine.dispose()


@pytest.mark.asyncio
async def test_extraction_reports_isolated_targets(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        workspace = await create_workspace(session, WorkspaceCreate(name="Research"))
        dataset = await create_dataset(
            session, DatasetCreate(workspace_id=workspace.id, name="Isolated")
        )
        await create_feature(
            session,
            FeatureCreate(
                dataset_id=dataset.id,
                geometry={"type": "LineString", "coordinates": [[0, 0], [1, 0]]},
                coordinate_space="local",
                crs=None,
            ),
        )
        preview = (
            await build_extraction_plan(
                session, SceneExtractionCreate(dataset_id=dataset.id, radius=5)
            )
        ).preview()

    assert preview.eligible_targets == 1
    assert preview.proposed_scenes == 0
    assert preview.isolated_targets == 1
    await engine.dispose()
