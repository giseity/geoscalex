from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from geoscalex.domain import DatasetCreate, FeatureCreate, RevisionCreate, WorkspaceCreate
from geoscalex.storage.models import Base
from geoscalex.storage.repository import (
    add_revision,
    create_dataset,
    create_feature,
    create_workspace,
    list_revisions,
    restore_revision,
)


@pytest.mark.asyncio
async def test_feature_creation_is_revisioned(tmp_path: Path) -> None:
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
                name="Sample",
                geometry={"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
            ),
        )
        original_revision = feature.current_revision
        feature = await add_revision(
            session,
            feature.id,
            RevisionCreate(
                geometry={"type": "LineString", "coordinates": [[0, 0], [1, 2], [2, 0]]}
            ),
        )
        feature = await restore_revision(session, feature.id, original_revision.id)
        revisions = await list_revisions(session, feature.id)

    assert feature.current_revision.sequence == 3
    assert feature.current_revision.change_kind == "restore-r1"
    assert len(revisions) == 3
    assert len(feature.current_revision.checksum) == 64
    await engine.dispose()
