from __future__ import annotations

import hashlib
import inspect
import math
import random
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

GeneratorFunction = Callable[[BaseModel, random.Random], dict[str, Any]]


class GeneratorDefinition(BaseModel):
    id: str
    name: str
    version: str
    description: str
    geometry_type: str
    parameter_schema: dict[str, Any]
    code_hash: str


class RegistryEntry(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    definition: GeneratorDefinition
    parameters: type[BaseModel]
    generate: GeneratorFunction


class CurveParameters(BaseModel):
    samples: int = Field(default=160, ge=8, le=5000)
    length: float = Field(default=10.0, gt=0, le=1000)
    amplitude: float = Field(default=1.0, ge=0, le=100)
    noise: float = Field(default=0.05, ge=0, le=10)
    frequency: float = Field(default=2.0, gt=0, le=50)


class ZigzagParameters(BaseModel):
    turns: int = Field(default=12, ge=2, le=1000)
    spacing: float = Field(default=1.0, gt=0, le=100)
    amplitude: float = Field(default=1.0, gt=0, le=100)
    jitter: float = Field(default=0.03, ge=0, le=10)


class HairpinParameters(BaseModel):
    samples: int = Field(default=180, ge=16, le=5000)
    radius: float = Field(default=2.0, gt=0, le=100)
    approach: float = Field(default=4.0, gt=0, le=100)
    noise: float = Field(default=0.02, ge=0, le=10)


class PolygonParameters(BaseModel):
    vertices: int = Field(default=64, ge=8, le=2000)
    radius: float = Field(default=4.0, gt=0, le=100)
    irregularity: float = Field(default=0.25, ge=0, le=0.8)
    lobes: int = Field(default=5, ge=1, le=30)


class HoledPolygonParameters(PolygonParameters):
    holes: int = Field(default=2, ge=1, le=8)
    hole_radius: float = Field(default=0.45, gt=0, le=2)


def _line(points: list[list[float]]) -> dict[str, Any]:
    return {"type": "LineString", "coordinates": points}


def noisy_straight(parameters: BaseModel, rng: random.Random) -> dict[str, Any]:
    p = CurveParameters.model_validate(parameters)
    return _line([[p.length * i / (p.samples - 1), rng.gauss(0, p.noise)] for i in range(p.samples)])


def smooth_curve(parameters: BaseModel, rng: random.Random) -> dict[str, Any]:
    p = CurveParameters.model_validate(parameters)
    return _line(
        [
            [
                p.length * i / (p.samples - 1),
                p.amplitude * math.sin(math.pi * i / (p.samples - 1)) + rng.gauss(0, p.noise),
            ]
            for i in range(p.samples)
        ]
    )


def meandering_river(parameters: BaseModel, rng: random.Random) -> dict[str, Any]:
    p = CurveParameters.model_validate(parameters)
    phases = [rng.uniform(0, math.tau) for _ in range(3)]
    points = []
    for i in range(p.samples):
        x = p.length * i / (p.samples - 1)
        t = x / p.length
        y = p.amplitude * (
            math.sin(math.tau * p.frequency * t + phases[0])
            + 0.35 * math.sin(math.tau * p.frequency * 0.47 * t + phases[1])
            + 0.15 * math.sin(math.tau * p.frequency * 2.3 * t + phases[2])
        )
        points.append([x, y + rng.gauss(0, p.noise)])
    return _line(points)


def zigzag(parameters: BaseModel, rng: random.Random) -> dict[str, Any]:
    p = ZigzagParameters.model_validate(parameters)
    return _line(
        [[i * p.spacing, (p.amplitude if i % 2 else -p.amplitude) + rng.gauss(0, p.jitter)] for i in range(p.turns + 1)]
    )


def hairpin(parameters: BaseModel, rng: random.Random) -> dict[str, Any]:
    p = HairpinParameters.model_validate(parameters)
    approach_count = max(2, p.samples // 4)
    curve_count = p.samples - 2 * approach_count
    points: list[list[float]] = []
    for i in range(approach_count):
        points.append([-p.approach + p.approach * i / approach_count, -p.radius])
    for i in range(curve_count):
        angle = -math.pi / 2 + math.pi * i / max(1, curve_count - 1)
        points.append([p.radius * math.cos(angle), p.radius * math.sin(angle)])
    for i in range(approach_count):
        points.append([-p.approach * i / max(1, approach_count - 1), p.radius])
    return _line([[x + rng.gauss(0, p.noise), y + rng.gauss(0, p.noise)] for x, y in points])


def irregular_polygon(parameters: BaseModel, rng: random.Random) -> dict[str, Any]:
    p = PolygonParameters.model_validate(parameters)
    phase = rng.uniform(0, math.tau)
    ring = []
    for i in range(p.vertices):
        angle = math.tau * i / p.vertices
        modulation = 1 + p.irregularity * math.sin(p.lobes * angle + phase)
        modulation += rng.uniform(-p.irregularity * 0.12, p.irregularity * 0.12)
        ring.append([p.radius * modulation * math.cos(angle), p.radius * modulation * math.sin(angle)])
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def polygon_with_holes(parameters: BaseModel, rng: random.Random) -> dict[str, Any]:
    p = HoledPolygonParameters.model_validate(parameters)
    exterior = irregular_polygon(p, rng)["coordinates"][0]
    holes: list[list[list[float]]] = []
    orbit = p.radius * 0.42
    for hole_index in range(p.holes):
        center_angle = math.tau * hole_index / p.holes
        cx, cy = orbit * math.cos(center_angle), orbit * math.sin(center_angle)
        ring = []
        for index in range(16):
            angle = -math.tau * index / 16
            radius = p.hole_radius * rng.uniform(0.85, 1.15)
            ring.append([cx + radius * math.cos(angle), cy + radius * math.sin(angle)])
        ring.append(ring[0])
        holes.append(ring)
    return {"type": "Polygon", "coordinates": [exterior, *holes]}


class GeneratorRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}

    def register(self, identifier: str, name: str, description: str, geometry_type: str, parameters: type[BaseModel], function: GeneratorFunction) -> None:
        definition = GeneratorDefinition(
            id=identifier,
            name=name,
            version="1",
            description=description,
            geometry_type=geometry_type,
            parameter_schema=parameters.model_json_schema(),
            code_hash=hashlib.sha256(inspect.getsource(function).encode()).hexdigest(),
        )
        self._entries[identifier] = RegistryEntry(definition=definition, parameters=parameters, generate=function)

    def definitions(self) -> list[GeneratorDefinition]:
        return [entry.definition for entry in self._entries.values()]

    def get(self, identifier: str) -> RegistryEntry:
        try:
            return self._entries[identifier]
        except KeyError as error:
            raise LookupError(f"Generator {identifier!r} not found") from error

    def run(self, identifier: str, parameters: dict[str, Any], seed: int) -> dict[str, Any]:
        entry = self.get(identifier)
        return entry.generate(entry.parameters.model_validate(parameters), random.Random(seed))


generator_registry = GeneratorRegistry()
generator_registry.register("noisy-straight", "Noisy straight", "Nearly straight digitized line.", "LineString", CurveParameters, noisy_straight)
generator_registry.register("smooth-curve", "Smooth curve", "Broad smooth bend with sampling noise.", "LineString", CurveParameters, smooth_curve)
generator_registry.register("meandering-river", "Meandering river", "Multiscale river-like oscillations.", "LineString", CurveParameters, meandering_river)
generator_registry.register("zigzag", "Zigzag", "Repeated alternating direction changes.", "LineString", ZigzagParameters, zigzag)
generator_registry.register("hairpin", "Hairpin", "A tight U-turn with approaches.", "LineString", HairpinParameters, hairpin)
generator_registry.register("irregular-polygon", "Irregular polygon", "A closed lobe-modulated polygon.", "Polygon", PolygonParameters, irregular_polygon)
generator_registry.register("polygon-with-holes", "Polygon with holes", "An irregular polygon with deterministic interior rings.", "Polygon", HoledPolygonParameters, polygon_with_holes)
