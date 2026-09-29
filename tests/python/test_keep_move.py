import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from geoscalex.domain import (
    DatasetCreate,
    FeatureCreate,
    SimplificationRunCreate,
    VertexCountBudget,
    WorkspaceCreate,
)
from geoscalex.geometry.analysis import GeometryValidationError, validate_geometry
from geoscalex.simplification.execution import execute_deepseek
from geoscalex.simplification.gateway import GatewayProposal
from geoscalex.simplification.keep_move import apply_keep_move, normalize_for_model
from geoscalex.storage import models
from geoscalex.storage.models import Base
from geoscalex.storage.repository import (
    create_dataset,
    create_feature,
    create_workspace,
    enqueue_simplification_run,
)


def test_line_keep_move_preserves_endpoints_and_exact_budget() -> None:
    source = {
        "type": "LineString",
        "coordinates": [[0, 0], [1, 0.2], [2, 1], [3, 0.2], [4, 0]],
    }
    normalized = normalize_for_model(source)
    candidate, metrics = apply_keep_move(
        normalized,
        [0, 2, 4],
        [(0.0, 0.0), (0.0, 0.02), (0.0, 0.0)],
        3,
    )
    assert validate_geometry(candidate).vertex_count == 3
    assert list(candidate["coordinates"][0]) == [0.0, 0.0]
    assert list(candidate["coordinates"][-1]) == [4.0, 0.0]
    assert metrics["moved_vertex_count"] == 1


def test_keep_move_rejects_moved_line_endpoint() -> None:
    normalized = normalize_for_model(
        {"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 0]]}
    )
    with pytest.raises(GeometryValidationError, match="must not move"):
        apply_keep_move(normalized, [0, 2], [(0.01, 0), (0, 0)], 2)


def test_polygon_keep_move_closes_generated_ring() -> None:
    normalized = normalize_for_model(
        {
            "type": "Polygon",
            "coordinates": [[[0, 0], [3, 0], [3, 3], [0, 3], [0, 0]]],
        }
    )
    candidate, _ = apply_keep_move(
        normalized,
        [0, 1, 2, 3],
        [(0, 0), (0, 0), (0, 0), (0, 0)],
        4,
    )
    assert candidate["coordinates"][0][0] == candidate["coordinates"][0][-1]


@pytest.mark.asyncio
async def test_deepseek_execution_persists_fake_provider_candidate(tmp_path, monkeypatch) -> None:
    async def fake_proposal(**_kwargs) -> GatewayProposal:
        return GatewayProposal.model_validate(
            {
                "keptIndices": [0, 2, 4],
                "offsets": [[0, 0], [0, 0.01], [0, 0]],
                "model": "fake-deepseek",
                "promptVersion": "test-v1",
                "promptHash": "prompt-hash",
                "usage": {"totalTokens": 12},
            }
        )

    monkeypatch.setattr("geoscalex.simplification.execution.request_proposal", fake_proposal)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        workspace = await create_workspace(session, WorkspaceCreate(name="Research"))
        dataset = await create_dataset(
            session, DatasetCreate(workspace_id=workspace.id, name="Curves")
        )
        feature = await create_feature(
            session,
            FeatureCreate(
                dataset_id=dataset.id,
                name="Line",
                geometry={
                    "type": "LineString",
                    "coordinates": [[0, 0], [1, 0.2], [2, 1], [3, 0.2], [4, 0]],
                },
            ),
        )
        request = SimplificationRunCreate(
            revision_id=feature.current_revision.id,
            method="deepseek-keep-move",
            budget=VertexCountBudget(value=3),
        )
        queued = await enqueue_simplification_run(session, request)
        job = await session.get(models.Job, str(queued.id))
        assert job is not None
        candidate = await execute_deepseek(session, job, request)

    assert candidate.method_kind == "llm"
    assert candidate.source_mapping == [0, 2, 4]
    assert candidate.metrics["budget_satisfied"] is True
    assert candidate.provenance["model"] == "fake-deepseek"
    await engine.dispose()
