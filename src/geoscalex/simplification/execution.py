from __future__ import annotations

import hashlib
import json
import time

from sqlalchemy.ext.asyncio import AsyncSession

from geoscalex.domain import CandidateRead, SimplificationRunCreate
from geoscalex.geometry.analysis import GeometryValidationError
from geoscalex.simplification.budget import resolve_budget
from geoscalex.simplification.gateway import request_proposal
from geoscalex.simplification.keep_move import apply_keep_move, normalize_for_model
from geoscalex.storage import models, repository


async def execute_deepseek(
    session: AsyncSession, job: models.Job, data: SimplificationRunCreate
) -> CandidateRead:
    revision = await repository.require(session, models.GeometryRevision, data.revision_id)
    normalized = normalize_for_model(revision.geometry_geojson)
    resolved = resolve_budget(revision.geometry_geojson, data.budget)
    errors: list[str] = []
    started = time.perf_counter()
    for attempt in range(1, 3):
        try:
            proposal = await request_proposal(
                geometry_type=normalized.geometry_type,
                coordinates=normalized.coordinates,
                budget=resolved.vertex_count,
                previous_errors=errors,
            )
            geometry, movement_metrics = apply_keep_move(
                normalized,
                proposal.kept_indices,
                proposal.offsets,
                resolved.vertex_count,
            )
            structured = proposal.model_dump(mode="json", by_alias=True)
            response_hash = hashlib.sha256(
                json.dumps(structured, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            return await repository.persist_generated_candidate(
                session,
                job=job,
                data=data,
                geometry=geometry,
                source_mapping=proposal.kept_indices,
                method_kind="llm",
                provenance={
                    "provider": "deepseek",
                    "model": proposal.model,
                    "prompt_version": proposal.prompt_version,
                    "prompt_hash": proposal.prompt_hash,
                    "response_hash": response_hash,
                    "usage": proposal.usage,
                },
                diagnostics={
                    "attempts": attempt,
                    "validation_errors": errors,
                    "fallback_used": False,
                },
                extra_metrics={
                    **movement_metrics,
                    "latency_ms": (time.perf_counter() - started) * 1000,
                },
            )
        except (GeometryValidationError, ValueError) as error:
            errors.append(str(error))
    raise ValueError(
        "DeepSeek did not produce a valid exact-budget candidate: " + "; ".join(errors)
    )
