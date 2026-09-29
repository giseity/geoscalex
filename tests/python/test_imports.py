from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from geoscalex.domain import DatasetCreate, GeoJsonImportCreate, WorkspaceCreate
from geoscalex.storage.models import Base
from geoscalex.storage.repository import (
    create_dataset,
    create_workspace,
    import_geojson,
    list_features,
)

COLLECTION = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "river-a",
            "properties": {"name": "River A", "basin": "north"},
            "geometry": {
                "type": "LineString",
                "coordinates": [[-80.0, 40.0], [-79.8, 40.1], [-79.6, 40.0]],
            },
        },
        {
            "type": "Feature",
            "id": "roads-b",
            "properties": {"name": "Roads B"},
            "geometry": {
                "type": "MultiLineString",
                "coordinates": [
                    [[-79.0, 40.0], [-78.9, 40.1]],
                    [[-79.0, 40.2], [-78.8, 40.3]],
                ],
            },
        },
        {
            "type": "Feature",
            "id": "area-c",
            "properties": {"name": "Area C", "basin": "south"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-78.0, 39.0], [-77.5, 39.0], [-77.5, 39.5], [-78.0, 39.0]]
                ],
            },
        },
        {
            "type": "Feature",
            "id": "unsupported",
            "properties": {},
            "geometry": {"type": "Point", "coordinates": [-77.0, 39.0]},
        },
    ],
}


@pytest.mark.asyncio
async def test_real_data_import_tracks_provenance_groups_and_multi_parts(
    tmp_path: Path,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'imports.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions() as session:
            workspace = await create_workspace(session, WorkspaceCreate(name="Real data"))
            dataset = await create_dataset(
                session,
                DatasetCreate(workspace_id=workspace.id, name="North American pilot"),
            )
            request = GeoJsonImportCreate(
                dataset_id=dataset.id,
                batch_name="Authoritative sample",
                feature_collection=COLLECTION,
                source_name="example-source",
                source_uri="https://example.test/data",
                source_license="public-domain-test-fixture",
                acquired_at="2026-09-29",
                source_file_name="sample.geojson",
                split_group_field="basin",
                split_grid_size=0.5,
                seed=17,
            )
            result = await import_geojson(session, request)
            features = await list_features(session, dataset.id)

        assert result.submitted == 4
        assert result.eligible == 4
        assert result.imported == 4
        assert result.sampled_out == 0
        assert len(result.rejected) == 1
        assert "Unsupported geometry type" in result.rejected[0]["reason"]
        assert result.batch.provenance["source_checksum_sha256"]
        assert result.batch.provenance["eligible_geometry_count"] == 4
        assert result.batch.provenance["declared"] == {}
        assert {feature.current_revision.geometry["type"] for feature in features} == {
            "LineString",
            "Polygon",
        }
        multi_parts = [feature for feature in features if feature.name.startswith("Roads B")]
        assert len(multi_parts) == 2
        assert {
            feature.current_revision.properties["_geoscalex_import"]["part_index"]
            for feature in multi_parts
        } == {0, 1}
        river = next(feature for feature in features if feature.name == "River A")
        assert river.current_revision.properties["split_group"].endswith(":basin:north")
        assert all(
            feature.current_revision.properties["split_group"]
            for feature in features
        )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_data_import_cap_is_order_independent(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sampling.sqlite3'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        selected: list[set[str]] = []
        async with sessions() as session:
            workspace = await create_workspace(session, WorkspaceCreate(name="Sampling"))
            for index, collection in enumerate(
                (COLLECTION, {**COLLECTION, "features": list(reversed(COLLECTION["features"]))})
            ):
                dataset = await create_dataset(
                    session,
                    DatasetCreate(workspace_id=workspace.id, name=f"Sample {index}"),
                )
                result = await import_geojson(
                    session,
                    GeoJsonImportCreate(
                        dataset_id=dataset.id,
                        feature_collection=collection,
                        source_name="stable-source",
                        source_id_field=None,
                        max_features=2,
                        seed=99,
                    ),
                )
                features = await list_features(session, dataset.id)
                selected.append(
                    {
                        feature.current_revision.properties["_geoscalex_import"][
                            "source_feature_id"
                        ]
                        for feature in features
                    }
                )
                assert result.sampled_out == 2
        assert selected[0] == selected[1]
    finally:
        await engine.dispose()
