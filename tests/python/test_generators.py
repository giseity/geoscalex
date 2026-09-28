from geoscalex.generators import generator_registry
from geoscalex.geometry.analysis import validate_geometry


def test_all_generators_are_deterministic_and_valid() -> None:
    for definition in generator_registry.definitions():
        first = generator_registry.run(definition.id, {}, 42)
        second = generator_registry.run(definition.id, {}, 42)
        assert first == second
        assert validate_geometry(first).geometry_type == definition.geometry_type
