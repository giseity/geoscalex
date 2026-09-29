import hashlib
import json
from collections import Counter
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from shapely import to_wkb
from shapely.geometry import shape
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from geoscalex.config import settings
from geoscalex.datasets.audit import audit_export
from geoscalex.datasets.io import assign_split, publish_dataset
from geoscalex.datasets.pilot import (
    LINE_GENERATORS,
    POLYGON_GENERATORS,
    PilotConfig,
    _covered_split_seed,
    build_pilot,
)
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
        audit = audit_export(export_dir)
        assert audit["ok"] is True
        assert audit["features"]["count"] == 2
    finally:
        settings.data_dir = old_data_dir
        await engine.dispose()


def test_dataset_audit_rejects_cross_split_duplicate_geometry(tmp_path: Path) -> None:
    geometry_wkb = to_wkb(shape({"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 0]]}))
    rows = [
        {
            "geometry_wkb": geometry_wkb,
            "geometry_type": "LineString",
            "properties_json": "{}",
            "source": "test",
            "coordinate_space": "local",
            "split_group": f"group-{split}",
            "split": split,
            "dp_scores": [None, 1.0, None],
            "vw_scores": [None, 1.0, None],
        }
        for split in ("train", "test")
    ]
    features_path = tmp_path / "features.parquet"
    pq.write_table(pa.Table.from_pylist(rows), features_path)
    checksum = hashlib.sha256(features_path.read_bytes()).hexdigest()
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "format": "geoscalex-dataset",
                "schema_version": 3,
                "dataset_id": "test",
                "version": 1,
                "feature_count": 2,
                "files": [{"path": "features.parquet", "sha256": checksum}],
            }
        ),
        encoding="utf-8",
    )
    report = audit_export(tmp_path)
    assert report["ok"] is False
    assert report["features"]["cross_split_duplicates"] == 1


def test_pilot_split_seed_covers_every_generator_family() -> None:
    families = (*LINE_GENERATORS, *POLYGON_GENERATORS)
    groups = {
        f"synthetic-pilot-v1:{family}:{index:03d}": family
        for family in families
        for index in range(24)
    }
    seed = _covered_split_seed(groups, 90_210)
    for family in families:
        assert {
            assign_split(group, seed)
            for group, group_family in groups.items()
            if group_family == family
        } == {"train", "validation", "test"}
    split_counts = Counter(assign_split(group, seed) for group in groups)
    assert split_counts["train"] / len(groups) == pytest.approx(0.8, abs=0.03)
    assert split_counts["validation"] / len(groups) == pytest.approx(0.1, abs=0.03)
    assert split_counts["test"] / len(groups) == pytest.approx(0.1, abs=0.03)


@pytest.mark.asyncio
async def test_pilot_builder_creates_balanced_audited_export(tmp_path: Path) -> None:
    old_data_dir = settings.data_dir
    settings.data_dir = tmp_path / "data"
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'pilot.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            result = await build_pilot(
                session,
                PilotConfig(
                    count=30,
                    polygon_fraction=0.5,
                    group_size=1,
                    workspace_name="Pilot tests",
                    dataset_name="Balanced pilot",
                    require_family_coverage=False,
                ),
            )
        audit = audit_export(Path(result["manifest_path"]).parent)
        assert result["line_count"] == 15
        assert result["polygon_count"] == 15
        assert audit["ok"] is True
        assert audit["features"]["geometry_types"] == {"LineString": 15, "Polygon": 15}
        assert audit["features"]["model_eligible"] == 30
        assert set(audit["features"]["generator_families"]) == {
            *LINE_GENERATORS,
            *POLYGON_GENERATORS,
        }
    finally:
        settings.data_dir = old_data_dir
        await engine.dispose()
