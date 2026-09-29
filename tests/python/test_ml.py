# ruff: noqa: E402, I001

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from shapely import to_wkb
from shapely.geometry import shape

torch = pytest.importorskip("torch")

from geoscalex.geometry.analysis import validate_geometry
from geoscalex.ml.data import collate, load_samples
from geoscalex.ml.evaluation import evaluate
from geoscalex.ml.experiment import run_experiment
from geoscalex.ml.features import FEATURE_DIM, vertex_features
from geoscalex.ml.inference import infer_geometry, load_checkpoint
from geoscalex.ml.model import ModelConfig, RemoveMoveEncoder
from geoscalex.ml.review_batch import score_review_priority
from geoscalex.ml.training import MODEL_PROFILES, _cutoff_weighted_loss, train
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
            "split_group": "fixture-1",
            "geometry_type": "LineString",
            "source": "test",
            "coordinate_space": "local",
            "properties_json": "{}",
            "geometry_wkb": to_wkb(shape(LINE)),
            "dp_scores": [None, 0.1, 0.8, 0.1, None],
            "vw_scores": [None, 0.1, 0.8, 0.1, None],
        }
    ]
    features_path = export_dir / "features.parquet"
    pq.write_table(pa.Table.from_pylist(rows), features_path)
    checksum = hashlib.sha256(features_path.read_bytes()).hexdigest()
    (export_dir / "manifest.json").write_text(
        json.dumps(
            {
                "format": "geoscalex-dataset",
                "schema_version": 3,
                "dataset_id": "fixture",
                "version": 1,
                "feature_count": 1,
                "files": [{"path": "features.parquet", "sha256": checksum}],
            }
        ),
        encoding="utf-8",
    )


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


def test_cutoff_weighted_loss_emphasizes_low_budget_boundary_errors() -> None:
    target = torch.tensor([1.1, 0.8, 0.51, 0.49, 0.1])
    retained = torch.tensor([True, True, True, False, False])
    near_boundary = target.clone()
    near_boundary[2] += 0.2
    far_from_boundary = target.clone()
    far_from_boundary[4] += 0.2

    near_loss = _cutoff_weighted_loss(near_boundary, target, retained, torch.tensor(0.1))
    far_loss = _cutoff_weighted_loss(far_from_boundary, target, retained, torch.tensor(0.1))

    assert near_loss > far_loss


def test_review_priority_records_low_budget_disagreement_components() -> None:
    model = RemoveMoveEncoder(
        ModelConfig(hidden_dim=16, layers=1, heads=2, feedforward_dim=32, dropout=0)
    )
    score = score_review_priority(
        model,
        LINE,
        feature_id="feature-1",
        feature_name="Fixture",
    )

    assert score.priority >= 0
    assert [item["retention_ratio"] for item in score.ratios] == [0.1, 0.25]
    assert all("teacher_method" in item for item in score.ratios)


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
    sample = load_samples(export_dir, split="train")[0]
    assert sample.teacher_method == "douglas-peucker"
    assert sample.dp_importance.tolist() == sample.vw_importance.tolist()
    assert sample.consensus_importance[0] == 1.0
    assert sample.importance[0] == pytest.approx(1.1)
    batch = collate([sample], importance_ratios=[0.5])
    assert int(batch["keep_mask"].sum()) == 3
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
    assert report["best_epoch"] == 1
    assert report["training_objective"] == "rank-regression"
    assert metadata["train_samples"] == 1
    assert metadata["torch_num_threads"] >= 1
    assert metadata["trainable_parameters"] > 0
    assert checkpoint.with_suffix(".pt.json").exists()
    evaluation = evaluate(export_dir, checkpoint, split="train", ratios=(0.5,))
    assert evaluation["budgets"] == [0.5]
    assert evaluation["encoder_cold_start_latency_ms"] >= 0
    assert evaluation["methods"]["encoder-remove-move"]["candidate_count"] == 1
    assert evaluation["methods"]["encoder-remove-move"]["mean_quality_teacher_topk_agreement"] >= 0
    assert evaluation["methods"]["teacher-quality-oracle"]["candidate_count"] == 1
    assert evaluation["methods"]["teacher-consensus-oracle"]["candidate_count"] == 1
    assert set(evaluation["methods"]["encoder-remove-move"]["by_geometry_type"]) == {"LineString"}
    assert evaluation["teacher_oracle_note"]
    assert evaluation["paired_comparisons"]["douglas-peucker"]["pair_count"] == 1
    assert evaluation["paired_comparisons"]["teacher-consensus-oracle"]["pair_count"] == 1
    assert (
        evaluation["teacher_comparisons"]["teacher-quality-oracle"]["douglas-peucker"]["pair_count"]
        == 1
    )
    assert evaluation["teacher_selection_counts"] == {"douglas-peucker": 1}
    experiment = run_experiment(
        export_dir,
        tmp_path / "experiment",
        profile="smoke",
        epochs=1,
        batch_size=1,
        ratios=(0.5,),
    )
    assert experiment["profile"] == "smoke"
    assert experiment["training_duration_seconds"] >= 0
    assert experiment["evaluation_duration_seconds"] >= 0
    assert experiment["experiment_version"] == 2
    assert experiment["runtime"]["python_version"]
    assert Path(experiment["checkpoint"]).exists()
