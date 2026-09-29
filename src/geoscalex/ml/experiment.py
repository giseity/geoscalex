from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from geoscalex.datasets.audit import audit_export
from geoscalex.ml.evaluation import evaluate
from geoscalex.ml.training import MODEL_PROFILES, train


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_experiment(
    export_dir: Path,
    output_dir: Path,
    *,
    profile: str = "smoke",
    epochs: int = 10,
    batch_size: int = 16,
    seed: int = 4_812,
    device: str = "cpu",
    threads: int | None = None,
    ratios: tuple[float, ...] = (0.1, 0.25, 0.5, 0.75),
) -> dict[str, Any]:
    if profile not in MODEL_PROFILES:
        raise ValueError(f"Unknown model profile: {profile}")
    export_dir = export_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    audit = audit_export(export_dir)
    audit_path = output_dir / "audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not audit["ok"]:
        raise ValueError(f"Dataset audit failed; see {audit_path}")

    checkpoint = output_dir / "checkpoint.pt"
    training = train(
        export_dir,
        checkpoint,
        epochs=epochs,
        batch_size=batch_size,
        seed=seed,
        device=device,
        model_config=MODEL_PROFILES[profile],
        model_profile=profile,
        threads=threads,
    )
    evaluation = evaluate(
        export_dir,
        checkpoint,
        split="test",
        device=device,
        ratios=ratios,
    )
    evaluation_path = output_dir / "evaluation.json"
    evaluation_path.write_text(
        json.dumps(evaluation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_path = export_dir / "manifest.json"
    report = {
        "experiment_version": 1,
        "experiment_id": output_dir.name,
        "dataset_manifest": str(manifest_path),
        "dataset_manifest_sha256": _checksum(manifest_path),
        "profile": profile,
        "epochs_requested": epochs,
        "batch_size": batch_size,
        "seed": seed,
        "device": device,
        "threads": threads,
        "ratios": list(ratios),
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": _checksum(checkpoint),
        "audit": str(audit_path),
        "training_report": str(checkpoint.with_suffix(".pt.json")),
        "evaluation_report": str(evaluation_path),
        "training_summary": {key: value for key, value in training.items() if key != "history"},
        "evaluation_summary": {
            "split": evaluation["split"],
            "sample_count": evaluation["sample_count"],
            "encoder_fallback_rate": evaluation["encoder_fallback_rate"],
            "methods": evaluation["methods"],
        },
    }
    report_path = output_dir / "experiment.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit, train, and evaluate one reproducible GeoScaleX experiment"
    )
    parser.add_argument("export_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--profile", choices=tuple(MODEL_PROFILES), default="smoke")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seed", type=int, default=4_812)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--threads", type=int)
    parser.add_argument("--ratios", default="0.1,0.25,0.5,0.75")
    arguments = parser.parse_args()
    ratios = tuple(float(value.strip()) for value in arguments.ratios.split(",") if value.strip())
    report = run_experiment(
        arguments.export_dir,
        arguments.output_dir,
        profile=arguments.profile,
        epochs=arguments.epochs,
        batch_size=arguments.batch_size,
        seed=arguments.seed,
        device=arguments.device,
        threads=arguments.threads,
        ratios=ratios,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def run() -> None:
    main()


if __name__ == "__main__":
    main()
