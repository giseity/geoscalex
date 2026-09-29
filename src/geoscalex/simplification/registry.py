from __future__ import annotations

from dataclasses import dataclass

from geoscalex.domain import GeometryKind, SimplificationMethodRead


@dataclass(frozen=True)
class MethodDefinition:
    id: str
    name: str
    version: str
    kind: str
    geometry_types: tuple[GeometryKind, ...]
    supports_holes: bool
    available: bool = True
    unavailable_reason: str | None = None

    def read(self) -> SimplificationMethodRead:
        return SimplificationMethodRead(
            id=self.id,
            name=self.name,
            version=self.version,
            kind=self.kind,
            geometry_types=list(self.geometry_types),
            supports_holes=self.supports_holes,
            available=self.available,
            unavailable_reason=self.unavailable_reason,
        )


class MethodRegistry:
    def __init__(self) -> None:
        supported = (GeometryKind.LINE_STRING, GeometryKind.POLYGON)
        self._methods = {
            "douglas-peucker": MethodDefinition(
                "douglas-peucker", "Douglas-Peucker", "1", "classical", supported, True
            ),
            "visvalingam-whyatt": MethodDefinition(
                "visvalingam-whyatt", "Visvalingam-Whyatt", "1", "classical", supported, True
            ),
            "deepseek-keep-move": MethodDefinition(
                "deepseek-keep-move",
                "DeepSeek keep-and-move",
                "1",
                "llm",
                supported,
                False,
                False,
                "The model gateway is not configured",
            ),
            "encoder-remove-move": MethodDefinition(
                "encoder-remove-move",
                "Neural remove-and-move encoder",
                "1",
                "neural",
                supported,
                False,
                False,
                "No encoder checkpoint is configured",
            ),
        }

    def get(self, method_id: str) -> MethodDefinition:
        try:
            return self._methods[method_id]
        except KeyError as error:
            raise LookupError(f"Unknown simplification method: {method_id}") from error

    def definitions(self) -> list[SimplificationMethodRead]:
        return [definition.read() for definition in self._methods.values()]


method_registry = MethodRegistry()
