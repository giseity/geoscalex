from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from geoscalex.domain import BatchCreate, FeatureCreate, GeneratorRunCreate, utc_now
from geoscalex.generators import generator_registry
from geoscalex.geometry.analysis import validate_geometry
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


async def execute(job_id: str) -> None:
    try:
        async with Session() as session:
            job = await repository.require(session, models.Job, job_id)
            kind = job.kind
        if kind == "generator-run":
            await execute_generator_job(job_id)
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
