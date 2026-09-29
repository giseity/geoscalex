from pathlib import Path

import duckdb
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from geoscalex.config import settings
from geoscalex.datasets.io import publish_dataset
from geoscalex.domain import (
    DatasetCreate,
    FeatureCreate,
    SceneCreate,
    SceneMemberCreate,
    WorkspaceCreate,
)
from geoscalex.storage.models import Base
from geoscalex.storage.repository import (
    create_dataset,
    create_feature,
    create_scene,
    create_workspace,
)


@pytest.mark.asyncio
async def test_publish_dataset_writes_verified_parquet(tmp_path: Path) -> None:
    old_data_dir = settings.data_dir
    settings.data_dir = tmp_path / "data"
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            workspace = await create_workspace(session, WorkspaceCreate(name="Research"))
            dataset = await create_dataset(
                session, DatasetCreate(workspace_id=workspace.id, name="Curves")
            )
            target = await create_feature(
                session,
                FeatureCreate(
                    dataset_id=dataset.id,
                    geometry={"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 0]]},
                ),
            )
            context = await create_feature(
                session,
                FeatureCreate(
                    dataset_id=dataset.id,
                    name="Context line",
                    geometry={"type": "LineString", "coordinates": [[0, 1], [2, 1]]},
                ),
            )
            await create_scene(
                session,
                SceneCreate(
                    dataset_id=dataset.id,
                    name="Pilot scene",
                    target_feature_id=target.id,
                    region="north-america",
                    provenance={"location_group": "great-lakes-001"},
                    members=[SceneMemberCreate(feature_id=context.id, role="sibling")],
                ),
            )
            version = await publish_dataset(session, dataset.id, 42)
        parquet = Path(version.manifest_path).parent / "features.parquet"
        export_dir = parquet.parent
        assert (export_dir / "candidates.parquet").exists()
        assert (export_dir / "annotations.parquet").exists()
        assert (export_dir / "scenes.parquet").exists()
        assert (export_dir / "scene_members.parquet").exists()
        assert (export_dir / "scene_reviews.parquet").exists()
        with duckdb.connect() as connection:
            assert (
                connection.execute(
                    "SELECT count(*) FROM read_parquet(?)", [str(parquet)]
                ).fetchone()[0]
                == 2
            )
            assert (
                connection.execute(
                    "SELECT count(*) FROM read_parquet(?)",
                    [str(export_dir / "scenes.parquet")],
                ).fetchone()[0]
                == 1
            )
            assert (
                connection.execute(
                    "SELECT count(*) FROM read_parquet(?)",
                    [str(export_dir / "scene_members.parquet")],
                ).fetchone()[0]
                == 2
            )
    finally:
        settings.data_dir = old_data_dir
        await engine.dispose()
