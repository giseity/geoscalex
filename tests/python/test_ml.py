# ruff: noqa: E402, I001

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from shapely import to_wkb
from shapely.geometry import shape

torch = pytest.importorskip("torch")

from geoscalex.geometry.analysis import validate_geometry
from geoscalex.ml.data import load_samples
from geoscalex.ml.evaluation import evaluate
from geoscalex.ml.features import FEATURE_DIM, vertex_features
from geoscalex.ml.inference import infer_geometry, load_checkpoint
from geoscalex.ml.model import ModelConfig, RemoveMoveEncoder
from geoscalex.ml.training import MODEL_PROFILES, train
from geoscalex.simplification.keep_move import normalize_for_model


LINE = {
    "type": "LineString",
    "coordinates": [[0, 0], [1, 0.2], [2, 1], [3, 0.2], [4, 0]],
}


def _export(export_dir: Path) -> None:
    export_dir.mkdir()
    rows = [
        {
            "revision_id": "revision-1",
            "split": "train",
            "geometry_wkb": to_wkb(shape(LINE)),
            "dp_scores": [None, 0.1, 0.8, 0.1, None],
            "vw_scores": [None, 0.1, 0.8, 0.1, None],
        }
    ]
    pq.write_table(pa.Table.from_pylist(rows), export_dir / "features.parquet")


def test_encoder_starts_with_zero_movement_and_emits_per_vertex_scores() -> None:
    normalized = normalize_for_model(LINE)
    features = torch.from_numpy(vertex_features(normalized))[None]
    model = RemoveMoveEncoder(
        ModelConfig(hidden_dim=16, layers=1, heads=2, feedforward_dim=32, dropout=0)
    )
    importance, movement = model(
        features,
        torch.zeros((1, 5), dtype=torch.bool),
        torch.tensor([0.6]),
    )
    assert importance.shape == (1, 5)
    assert movement.shape == (1, 5, 2)
    assert features.shape[-1] == FEATURE_DIM
    assert torch.count_nonzero(movement) == 0


def test_checkpoint_inference_preserves_line_endpoints_and_exact_budget(tmp_path: Path) -> None:
    config = ModelConfig(hidden_dim=16, layers=1, heads=2, feedforward_dim=32, dropout=0)
    model = RemoveMoveEncoder(config)
    checkpoint = tmp_path / "encoder.pt"
    torch.save(
        {
            "model_config": config.dict(),
            "model_state": model.state_dict(),
            "metadata": {"test": True},
        },
        checkpoint,
    )
    loaded, metadata = load_checkpoint(checkpoint)
    candidate, mapping, scores, diagnostics, movement = infer_geometry(loaded, LINE, 3)
    assert metadata == {"test": True}
    assert validate_geometry(candidate).vertex_count == 3
    assert mapping[0] == 0 and mapping[-1] == 4
    assert len(scores) == 5
    assert diagnostics["fallback_used"] is False
    assert movement["moved_vertex_count"] == 0


def test_training_writes_a_reloadable_checkpoint(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    _export(export_dir)
    assert len(load_samples(export_dir, split="train")) == 1
    checkpoint = tmp_path / "checkpoints" / "encoder.pt"
    report = train(
        export_dir,
        checkpoint,
        epochs=1,
        batch_size=1,
        seed=7,
        model_config=MODEL_PROFILES["smoke"],
        model_profile="smoke",
    )
    _, metadata = load_checkpoint(checkpoint)
    assert report["epochs_completed"] == 1
    assert metadata["train_samples"] == 1
    assert checkpoint.with_suffix(".pt.json").exists()
    evaluation = evaluate(export_dir, checkpoint, split="train", ratios=(0.5,))
    assert evaluation["budgets"] == [0.5]
    assert evaluation["methods"]["encoder-remove-move"]["candidate_count"] == 1
