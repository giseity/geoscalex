from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from geoscalex.datasets.audit import audit_export
from geoscalex.datasets.io import assign_split, publish_dataset
from geoscalex.domain import BatchCreate, DatasetCreate, FeatureCreate, WorkspaceCreate
from geoscalex.generators import generator_registry
from geoscalex.storage import models, repository
from geoscalex.storage.db import Session, init_database

RECIPE_VERSION = "synthetic-pilot-v1"
LINE_GENERATORS = (
    "noisy-straight",
    "smooth-curve",
    "meandering-river",
    "zigzag",
    "hairpin",
)
POLYGON_GENERATORS = ("irregular-polygon", "urban-footprint", "indented-polygon")
STRATA = ("low", "medium", "high")


@dataclass(frozen=True)
class PilotConfig:
    count: int = 1_000
    polygon_fraction: float = 0.5
    seed: int = 4_812
    split_seed: int = 90_210
    group_size: int = 10
    workspace_name: str = "GeoScaleX research"
    dataset_name: str = "Synthetic pilot 1k"
    require_family_coverage: bool = True

    def validate(self) -> None:
        if self.count < 12:
            raise ValueError("A pilot requires at least 12 geometries")
        if not 0.1 <= self.polygon_fraction <= 0.9:
            raise ValueError("polygon_fraction must be between 0.1 and 0.9")
        if self.group_size < 1:
            raise ValueError("group_size must be positive")


def _allocation(count: int, keys: tuple[str, ...]) -> dict[str, int]:
    base, remainder = divmod(count, len(keys))
    return {key: base + int(index < remainder) for index, key in enumerate(keys)}


def _vertex_range(stratum: str) -> tuple[int, int]:
    return {
        "low": (24, 64),
        "medium": (65, 192),
        "high": (193, 480),
    }[stratum]


def _parameters(generator_id: str, stratum: str, rng: random.Random) -> dict[str, Any]:
    low, high = _vertex_range(stratum)
    if generator_id in {"noisy-straight", "smooth-curve", "meandering-river"}:
        return {
            "samples": rng.randint(low, high),
            "length": round(rng.uniform(5.0, 40.0), 6),
            "amplitude": round(rng.uniform(0.15, 5.0), 6),
            "noise": round(rng.uniform(0.002, 0.18), 6),
            "frequency": round(rng.uniform(0.5, 8.0), 6),
        }
    if generator_id == "zigzag":
        return {
            "turns": rng.randint(max(2, low - 1), min(479, high - 1)),
            "spacing": round(rng.uniform(0.1, 3.0), 6),
            "amplitude": round(rng.uniform(0.2, 4.0), 6),
            "jitter": round(rng.uniform(0.001, 0.15), 6),
        }
    if generator_id == "hairpin":
        return {
            "samples": rng.randint(max(32, low), high),
            "radius": round(rng.uniform(0.4, 8.0), 6),
            "approach": round(rng.uniform(1.0, 15.0), 6),
            "noise": round(rng.uniform(0.001, 0.12), 6),
        }
    if generator_id == "irregular-polygon":
        return {
            "vertices": rng.randint(low, high),
            "radius": round(rng.uniform(1.0, 20.0), 6),
            "irregularity": round(rng.uniform(0.04, 0.55), 6),
            "lobes": rng.randint(2, 14),
        }
    if generator_id == "urban-footprint":
        return {
            "vertices": rng.randint(low, high),
            "width": round(rng.uniform(3.0, 30.0), 6),
            "height": round(rng.uniform(2.0, 18.0), 6),
            "squareness": round(rng.uniform(2.5, 12.0), 6),
            "irregularity": round(rng.uniform(0.005, 0.12), 6),
            "rotation": round(rng.uniform(-math.pi, math.pi), 6),
        }
    if generator_id == "indented-polygon":
        return {
            "vertices": rng.randint(max(24, low), high),
            "radius": round(rng.uniform(2.0, 20.0), 6),
            "depth": round(rng.uniform(0.2, 0.7), 6),
            "spread": round(rng.uniform(0.2, 0.9), 6),
            "irregularity": round(rng.uniform(0.01, 0.18), 6),
        }
    raise LookupError(f"Pilot recipe does not support generator {generator_id}")


def _covered_split_seed(
    groups: dict[str, str], requested_seed: int, *, maximum_attempts: int = 50_000
) -> int:
    required = {"train", "validation", "test"}
    families = set(groups.values())
    for seed in range(requested_seed, requested_seed + maximum_attempts):
        observed: dict[str, set[str]] = {family: set() for family in families}
        for group, family in groups.items():
            observed[family].add(assign_split(group, seed))
        if all(splits == required for splits in observed.values()):
            return seed
    raise RuntimeError(
        f"Could not find a family-covered split seed in {maximum_attempts} attempts; "
        "decrease group_size or allow incomplete family splits"
    )


async def _workspace(session: AsyncSession, name: str) -> models.Workspace:
    existing = await session.scalar(
        select(models.Workspace).where(models.Workspace.name == name).order_by(models.Workspace.id)
    )
    if existing is not None:
        return existing
    created = await repository.create_workspace(session, WorkspaceCreate(name=name))
    return await repository.require(session, models.Workspace, created.id)


async def build_pilot(
    session: AsyncSession,
    config: PilotConfig,
    *,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    config.validate()
    workspace = await _workspace(session, config.workspace_name)
    dataset = await repository.create_dataset(
        session,
        DatasetCreate(
            workspace_id=workspace.id,
            name=config.dataset_name,
            description=(
                f"Deterministic {RECIPE_VERSION} benchmark with {config.count} geometries, "
                f"seed {config.seed}."
            ),
        ),
    )
    polygon_count = int(config.count * config.polygon_fraction + 0.5)
    line_count = config.count - polygon_count
    counts = _allocation(line_count, LINE_GENERATORS)
    counts.update(_allocation(polygon_count, POLYGON_GENERATORS))
    created = 0
    batch_cache: dict[str, str] = {}
    group_families: dict[str, str] = {}

    for generator_id, family_count in counts.items():
        entry = generator_registry.get(generator_id)
        for family_index in range(family_count):
            stratum = STRATA[family_index % len(STRATA)]
            stratum_index = family_index // len(STRATA)
            group_index = stratum_index // config.group_size
            split_group = f"{RECIPE_VERSION}:{generator_id}:{stratum}:{group_index:04d}"
            group_families[split_group] = generator_id
            batch_id = batch_cache.get(split_group)
            if batch_id is None:
                batch = await repository.create_batch(
                    session,
                    BatchCreate(
                        dataset_id=dataset.id,
                        name=f"{entry.definition.name} · {stratum} · {group_index + 1}",
                        source="synthetic-pilot",
                        provenance={
                            "recipe": RECIPE_VERSION,
                            "generator_id": generator_id,
                            "generator_version": entry.definition.version,
                            "code_hash": entry.definition.code_hash,
                            "stratum": stratum,
                            "group_index": group_index,
                            "split_group": split_group,
                        },
                    ),
                )
                batch_id = str(batch.id)
                batch_cache[split_group] = batch_id
            sample_seed = config.seed + created * 7_919
            parameter_rng = random.Random(sample_seed ^ 0x5F3759DF)
            parameters = _parameters(generator_id, stratum, parameter_rng)
            geometry = generator_registry.run(generator_id, parameters, sample_seed)
            await repository.create_feature(
                session,
                FeatureCreate(
                    dataset_id=dataset.id,
                    batch_id=batch_id,
                    name=f"{entry.definition.name} {family_index + 1:05d}",
                    geometry=geometry,
                    properties={
                        "recipe": RECIPE_VERSION,
                        "generator_id": generator_id,
                        "generator_version": entry.definition.version,
                        "generator_code_hash": entry.definition.code_hash,
                        "generator_parameters": parameters,
                        "seed": sample_seed,
                        "stratum": stratum,
                        "split_group": split_group,
                    },
                    coordinate_space="local",
                    crs=None,
                    source="synthetic-pilot",
                ),
            )
            created += 1
            if progress is not None:
                progress(created, config.count)

    split_seed = (
        _covered_split_seed(group_families, config.split_seed)
        if config.require_family_coverage
        else config.split_seed
    )
    version = await publish_dataset(session, dataset.id, split_seed)
    export_dir = Path(version.manifest_path).parent
    audit = audit_export(export_dir)
    audit_path = export_dir / "audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "recipe": RECIPE_VERSION,
        "workspace_id": str(workspace.id),
        "dataset_id": str(dataset.id),
        "dataset_version_id": str(version.id),
        "manifest_path": version.manifest_path,
        "audit_path": str(audit_path),
        "feature_count": created,
        "line_count": line_count,
        "polygon_count": polygon_count,
        "requested_split_seed": config.split_seed,
        "resolved_split_seed": split_seed,
        "audit_ok": audit["ok"],
        "audit_warnings": audit["warnings"],
    }


async def _run(arguments: argparse.Namespace) -> dict[str, Any]:
    await init_database()
    config = PilotConfig(
        count=arguments.count,
        polygon_fraction=arguments.polygon_fraction,
        seed=arguments.seed,
        split_seed=arguments.split_seed,
        group_size=arguments.group_size,
        workspace_name=arguments.workspace,
        dataset_name=arguments.dataset_name,
        require_family_coverage=not arguments.allow_incomplete_family_splits,
    )
    last_reported = 0

    def progress(created: int, total: int) -> None:
        nonlocal last_reported
        interval = max(1, total // 10)
        if created == total or created - last_reported >= interval:
            print(f"Generated {created}/{total} geometries", file=sys.stderr)
            last_reported = created

    async with Session() as session:
        return await build_pilot(session, config, progress=progress)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a deterministic synthetic pilot dataset")
    parser.add_argument("--count", type=int, default=1_000)
    parser.add_argument("--polygon-fraction", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=4_812)
    parser.add_argument("--split-seed", type=int, default=90_210)
    parser.add_argument("--group-size", type=int, default=10)
    parser.add_argument("--workspace", default="GeoScaleX research")
    parser.add_argument("--dataset-name", default="Synthetic pilot 1k")
    parser.add_argument("--allow-incomplete-family-splits", action="store_true")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = asyncio.run(_run(arguments))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not report["audit_ok"]:
        raise SystemExit(1)


def run() -> None:
    main()


if __name__ == "__main__":
    main()
