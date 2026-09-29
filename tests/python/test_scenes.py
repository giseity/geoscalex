from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from geoscalex.domain import (
    AnnotationChoice,
    CandidateCreate,
    DatasetCreate,
    FeatureCreate,
    SceneCreate,
    SceneMemberCreate,
    SceneReviewCreate,
    WorkspaceCreate,
)
from geoscalex.storage.models import Base
from geoscalex.storage.repository import (
    create_candidate,
    create_dataset,
    create_feature,
    create_scene,
    create_scene_review,
    create_workspace,
    list_scene_reviews,
    list_scenes,
)


@pytest.mark.asyncio
async def test_contextual_scene_and_review_are_revision_safe(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        workspace = await create_workspace(session, WorkspaceCreate(name="Research"))
        dataset = await create_dataset(
            session, DatasetCreate(workspace_id=workspace.id, name="Context")
        )
        target = await create_feature(
            session,
            FeatureCreate(
                dataset_id=dataset.id,
                name="River target",
                geometry={
                    "type": "LineString",
                    "coordinates": [[0, 0], [1, 0.25], [2, 0]],
                },
            ),
        )
        sibling = await create_feature(
            session,
            FeatureCreate(
                dataset_id=dataset.id,
                name="Nearby road",
                geometry={"type": "LineString", "coordinates": [[0, 1], [2, 1]]},
            ),
        )
        scene = await create_scene(
            session,
            SceneCreate(
                dataset_id=dataset.id,
                name="Rhine pilot scene",
                target_feature_id=target.id,
                region="europe",
                locality="Rhine basin",
                scale_denominator=50_000,
                provenance={"location_group": "rhine-001"},
                members=[SceneMemberCreate(feature_id=sibling.id, role="sibling")],
            ),
        )
        candidate_a = await create_candidate(
            session,
            CandidateCreate(
                revision_id=target.current_revision.id,
                method="douglas-peucker",
                vertex_budget=2,
            ),
        )
        candidate_b = await create_candidate(
            session,
            CandidateCreate(
                revision_id=target.current_revision.id,
                method="visvalingam-whyatt",
                vertex_budget=2,
            ),
        )
        review = await create_scene_review(
            session,
            SceneReviewCreate(
                scene_id=scene.id,
                revision_id=target.current_revision.id,
                candidate_a_id=candidate_a.id,
                candidate_b_id=candidate_b.id,
                choice=AnnotationChoice.EQUAL,
                acceptability="acceptable",
                failure_tags=["context-inconsistency"],
            ),
        )
        scenes = await list_scenes(session, dataset.id)
        reviews = await list_scene_reviews(session, scene.id)

    assert [member.role.value for member in scene.members] == ["sibling", "target"]
    assert scene.members[0].feature.name == "Nearby road"
    assert scenes[0].provenance["location_group"] == "rhine-001"
    assert review.failure_tags[0].value == "context-inconsistency"
    assert reviews[0].id == review.id
    await engine.dispose()


@pytest.mark.asyncio
async def test_scene_rejects_repeated_target(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        workspace = await create_workspace(session, WorkspaceCreate(name="Research"))
        dataset = await create_dataset(
            session, DatasetCreate(workspace_id=workspace.id, name="Context")
        )
        target = await create_feature(
            session,
            FeatureCreate(
                dataset_id=dataset.id,
                geometry={"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            ),
        )
        with pytest.raises(ValueError, match="target is added automatically"):
            await create_scene(
                session,
                SceneCreate(
                    dataset_id=dataset.id,
                    name="Invalid scene",
                    target_feature_id=target.id,
                    members=[SceneMemberCreate(feature_id=target.id)],
                ),
            )

    await engine.dispose()
