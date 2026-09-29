from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field

from geoscalex.config import settings


class GatewayProposal(BaseModel):
    kept_indices: list[int] = Field(alias="keptIndices")
    offsets: list[tuple[float, float]]
    model: str
    prompt_version: str = Field(alias="promptVersion")
    prompt_hash: str = Field(alias="promptHash")
    usage: dict[str, int | None] = Field(default_factory=dict)


async def gateway_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=0.75) as client:
            response = await client.get(f"{settings.model_gateway_url}/health")
        response.raise_for_status()
        return bool(response.json().get("configured"))
    except (httpx.HTTPError, ValueError):
        return False


async def request_proposal(
    *,
    geometry_type: str,
    coordinates: list[list[float]],
    budget: int,
    previous_errors: list[str],
) -> GatewayProposal:
    payload: dict[str, Any] = {
        "geometryType": geometry_type,
        "coordinates": coordinates,
        "budget": budget,
        "maxDisplacement": 0.05,
        "previousErrors": previous_errors,
    }
    async with httpx.AsyncClient(timeout=65.0) as client:
        response = await client.post(f"{settings.model_gateway_url}/v1/simplify", json=payload)
    if response.is_error:
        detail = response.json().get("error", response.text)
        raise ValueError(f"Model gateway rejected the request: {detail}")
    return GatewayProposal.model_validate(response.json())
