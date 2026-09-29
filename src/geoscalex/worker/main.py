from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from geoscalex.domain import (
    BatchCreate,
    FeatureCreate,
    GeneratorRunCreate,
    SceneExtractionCreate,
    SimplificationRunCreate,
    utc_now,
)
from geoscalex.generators import generator_registry
from geoscalex.geometry.analysis import validate_geometry
from geoscalex.scenes.extraction import build_extraction_plan
from geoscalex.simplification.execution import execute_deepseek, execute_encoder
from geoscalex.storage import models, repository
from geoscalex.storage.db import Session, init_database

logger = logging.getLogger(__name__)


async def claim_job() -> str | None:
    async with Session() as session:
        job = await session.scalar(
            select(models.Job)
            .where(models.Job.status == "queued")
            .order_by(models.Job.created_at)
            .limit(1)
        )
        if job is None:
            return None
        if job.cancel_requested:
            job.status = "cancelled"
            job.finished_at = utc_now()
            await session.commit()
            return None
        job.status = "running"
        job.started_at = utc_now()
        job.logs = [*job.logs, "Job started"]
        await session.commit()
        return job.id


async def execute_generator_job(job_id: str) -> None:
    async with Session() as session:
        job = await repository.require(session, models.Job, job_id)
        payload = GeneratorRunCreate.model_validate(job.payload)
        entry = generator_registry.get(payload.generator_id)
        batch = await repository.create_batch(
            session,
            BatchCreate(
                dataset_id=payload.dataset_id,
                name=payload.batch_name,
                source="generator",
                provenance={
                    "generator_id": entry.definition.id,
                    "generator_version": entry.definition.version,
                    "code_hash": entry.definition.code_hash,
                    "parameters": payload.parameters,
                    "seed": payload.seed,
                    "count": payload.count,
                    "job_id": job.id,
                },
            ),
        )
        created: list[str] = []
        for index in range(payload.count):
            await session.refresh(job)
            if job.cancel_requested:
                job.status = "cancelled"
                job.finished_at = utc_now()
                job.logs = [*job.logs, f"Cancelled after {len(created)} samples"]
                await session.commit()
                return
            sample_seed = payload.seed + index
            geometry = generator_registry.run(payload.generator_id, payload.parameters, sample_seed)
            validate_geometry(geometry)
            feature = await repository.create_feature(
                session,
                FeatureCreate(
                    dataset_id=payload.dataset_id,
                    batch_id=batch.id,
                    name=f"{entry.definition.name} {index + 1:04d}",
                    geometry=geometry,
                    properties={
                        "generator_id": entry.definition.id,
                        "generator_version": entry.definition.version,
                        "seed": sample_seed,
                    },
                    coordinate_space="local",
                    crs=None,
                    source="synthetic",
                ),
            )
            created.append(str(feature.id))
            job.progress = (index + 1) / payload.count
            if (index + 1) % 25 == 0 or index + 1 == payload.count:
                job.logs = [*job.logs, f"Generated {index + 1}/{payload.count} samples"]
            await session.commit()
        job.status = "succeeded"
        job.result = {"batch_id": str(batch.id), "feature_ids": created}
        job.finished_at = utc_now()
        job.logs = [*job.logs, "Job completed"]
        await session.commit()


async def execute_scene_extraction_job(job_id: str) -> None:
    async with Session() as session:
        job = await repository.require(session, models.Job, job_id)
        payload = SceneExtractionCreate.model_validate(job.payload)
        plan = await build_extraction_plan(session, payload)
        total = len(plan.scenes)
        job.logs = [
            *job.logs,
            f"Planned {total} scenes from {plan.eligible_targets} eligible targets",
        ]
        await session.commit()
        created: list[str] = []
        for index, planned in enumerate(plan.scenes):
            await session.refresh(job)
            if job.cancel_requested:
                job.status = "cancelled"
                job.result = {
                    "scene_ids": created,
                    "created": len(created),
                    "planned": total,
                    "isolated_targets": plan.isolated_targets,
                    "existing_targets": plan.existing_targets,
                    "incompatible_features": plan.incompatible_features,
                }
                job.finished_at = utc_now()
                job.logs = [*job.logs, f"Cancelled after {len(created)} scenes"]
                await session.commit()
                return
            scene = await repository.create_scene(session, planned.create)
            created.append(str(scene.id))
            job.progress = (index + 1) / total if total else 1.0
            if (index + 1) % 25 == 0 or index + 1 == total:
                job.logs = [*job.logs, f"Created {index + 1}/{total} scenes"]
            await session.commit()
        job.progress = 1.0
        job.status = "succeeded"
        job.result = {
            "scene_ids": created,
            "created": len(created),
            "planned": total,
            "isolated_targets": plan.isolated_targets,
            "existing_targets": plan.existing_targets,
            "incompatible_features": plan.incompatible_features,
            "role_counts": {role.value: count for role, count in plan.role_counts.items()},
        }
        job.finished_at = utc_now()
        job.logs = [*job.logs, "Scene extraction completed"]
        await session.commit()


async def execute_simplification_job(job_id: str) -> None:
    async with Session() as session:
        job = await repository.require(session, models.Job, job_id)
        payload = SimplificationRunCreate.model_validate(job.payload)
        if payload.method in {"douglas-peucker", "visvalingam-whyatt"}:
            candidate = await repository.execute_classical_simplification(session, job, payload)
        elif payload.method == "deepseek-keep-move":
            candidate = await execute_deepseek(session, job, payload)
        elif payload.method == "encoder-remove-move":
            candidate = await execute_encoder(session, job, payload)
        else:
            raise ValueError(f"Worker does not yet support method: {payload.method}")
        await session.refresh(job)
        if job.cancel_requested:
            job.status = "cancelled"
            job.result = {"discarded_candidate_id": str(candidate.id)}
            job.finished_at = utc_now()
            job.logs = [*job.logs, "Cancelled after candidate generation"]
            await session.commit()
            return
        job.progress = 1.0
        job.status = "succeeded"
        job.result = {"candidate_ids": [str(candidate.id)]}
        job.finished_at = utc_now()
        job.logs = [*job.logs, "Simplification candidate created"]
        await session.commit()


async def execute(job_id: str) -> None:
    try:
        async with Session() as session:
            job = await repository.require(session, models.Job, job_id)
            kind = job.kind
        if kind == "generator-run":
            await execute_generator_job(job_id)
        elif kind == "scene-extraction":
            await execute_scene_extraction_job(job_id)
        elif kind == "simplification-run":
            await execute_simplification_job(job_id)
        else:
            raise ValueError(f"Unknown job kind: {kind}")
    except Exception as error:
        logger.exception("Job %s failed", job_id)
        async with Session() as session:
            job = await repository.require(session, models.Job, job_id)
            job.status = "failed"
            job.error = str(error)
            job.finished_at = utc_now()
            job.logs = [*job.logs, f"Failed: {error}"]
            await session.commit()


async def serve() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_database()
    logger.info("GeoScaleX worker ready")
    while True:
        job_id = await claim_job()
        if job_id:
            await execute(job_id)
        else:
            await asyncio.sleep(1)


def run() -> None:
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("GeoScaleX worker stopped")


if __name__ == "__main__":
    run()
