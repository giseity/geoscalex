from __future__ import annotations

import argparse
import json
import random
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as functional

from geoscalex.ml.data import TrainingSample, collate, load_samples
from geoscalex.ml.model import ModelConfig, RemoveMoveEncoder


def _batches(
    samples: list[TrainingSample], batch_size: int, *, shuffle: bool, seed: int
) -> Iterator[list[TrainingSample]]:
    ordered = sorted(samples, key=lambda sample: len(sample.features))
    batches = [ordered[index : index + batch_size] for index in range(0, len(ordered), batch_size)]
    if shuffle:
        random.Random(seed).shuffle(batches)
    yield from batches


def _losses(
    model: RemoveMoveEncoder, batch: dict[str, torch.Tensor], device: str
) -> tuple[torch.Tensor, dict[str, float]]:
    tensors = {name: value.to(device) for name, value in batch.items()}
    importance, movement = model(
        tensors["features"], tensors["padding_mask"], tensors["budget_ratio"]
    )
    valid = ~tensors["padding_mask"]
    importance_loss = functional.smooth_l1_loss(importance[valid], tensors["importance"][valid])
    movement_mask = tensors["movement_mask"] & valid
    if movement_mask.any():
        movement_loss = functional.smooth_l1_loss(
            movement[movement_mask], tensors["movement"][movement_mask]
        )
    else:
        movement_loss = movement.sum() * 0.0
    displacement_penalty = movement[valid].square().mean()
    total = importance_loss + 2.0 * movement_loss + 0.01 * displacement_penalty
    return total, {
        "importance": float(importance_loss.detach().cpu()),
        "movement": float(movement_loss.detach().cpu()),
        "displacement_penalty": float(displacement_penalty.detach().cpu()),
        "total": float(total.detach().cpu()),
    }


def _epoch(
    model: RemoveMoveEncoder,
    samples: list[TrainingSample],
    *,
    batch_size: int,
    device: str,
    optimizer: torch.optim.Optimizer | None,
    seed: int,
) -> dict[str, float]:
    model.train(optimizer is not None)
    totals: dict[str, float] = {}
    seen = 0
    for sample_batch in _batches(samples, batch_size, shuffle=optimizer is not None, seed=seed):
        batch = collate(sample_batch)
        if optimizer is not None:
            optimizer.zero_grad(set_to_none=True)
            loss, values = _losses(model, batch, device)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        else:
            with torch.no_grad():
                _, values = _losses(model, batch, device)
        count = len(sample_batch)
        seen += count
        for name, value in values.items():
            totals[name] = totals.get(name, 0.0) + value * count
    return {name: value / seen for name, value in totals.items()}


def train(
    export_dir: Path,
    output: Path,
    *,
    epochs: int = 30,
    batch_size: int = 16,
    seed: int = 4812,
    device: str = "cpu",
) -> dict[str, Any]:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    train_samples = load_samples(export_dir, split="train")
    validation_samples = load_samples(export_dir, split="validation")
    if not train_samples:
        raise ValueError(f"No train samples found in {export_dir}")
    validation_fallback = not validation_samples
    if validation_fallback:
        validation_samples = train_samples

    config = ModelConfig()
    model = RemoveMoveEncoder(config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    best_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    history: list[dict[str, Any]] = []
    remaining_patience = 5
    for epoch in range(1, epochs + 1):
        train_metrics = _epoch(
            model,
            train_samples,
            batch_size=batch_size,
            device=device,
            optimizer=optimizer,
            seed=seed + epoch,
        )
        validation_metrics = _epoch(
            model,
            validation_samples,
            batch_size=batch_size,
            device=device,
            optimizer=None,
            seed=seed,
        )
        history.append({"epoch": epoch, "train": train_metrics, "validation": validation_metrics})
        if validation_metrics["total"] < best_loss - 1e-6:
            best_loss = validation_metrics["total"]
            best_state = {
                name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()
            }
            remaining_patience = 5
        else:
            remaining_patience -= 1
            if remaining_patience == 0:
                break

    if best_state is None:
        raise RuntimeError("Training did not produce a checkpoint")
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "format_version": 1,
        "dataset_path": str(export_dir.resolve()),
        "seed": seed,
        "train_samples": len(train_samples),
        "validation_samples": len(validation_samples),
        "validation_fallback": validation_fallback,
        "best_validation_loss": best_loss,
        "epochs_completed": len(history),
    }
    torch.save(
        {"model_config": config.dict(), "model_state": best_state, "metadata": metadata},
        output,
    )
    report = {**metadata, "checkpoint": str(output.resolve()), "history": history}
    output.with_suffix(output.suffix + ".json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the GeoScaleX remove-and-move encoder")
    parser.add_argument("export_dir", type=Path, help="Published dataset version directory")
    parser.add_argument("--output", type=Path, required=True, help="Checkpoint output path")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seed", type=int, default=4812)
    parser.add_argument("--device", default="cpu")
    arguments = parser.parse_args()
    report = train(
        arguments.export_dir,
        arguments.output,
        epochs=arguments.epochs,
        batch_size=arguments.batch_size,
        seed=arguments.seed,
        device=arguments.device,
    )
    print(json.dumps({key: value for key, value in report.items() if key != "history"}, indent=2))


def run() -> None:
    main()


if __name__ == "__main__":
    main()
