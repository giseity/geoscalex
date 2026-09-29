# Pilot Benchmark v0.5

GeoScaleX v0.5 moves from a functioning experiment loop to its first reproducible empirical
result. The milestone is intentionally synthetic-first: it validates dataset composition,
training, checkpoint inference, and matched-budget reporting before third-party GIS licensing or
large downloads become part of the workflow.

## Outcome

One command creates and publishes a balanced, deterministic pilot dataset. A second command audits
the export for leakage, composition, model eligibility, and supervision coverage. The existing
training and evaluation commands then produce a checkpoint and a report whose inputs can be traced
back to generator versions, parameter strata, and seeds.

The pilot is successful when the complete pipeline runs locally and exposes its limitations. It is
not evidence that the encoder is better than a classical simplifier.

## Synthetic pilot

The default pilot contains 1,000 geometries:

- 500 lines distributed across every exterior-line generator;
- 500 simple exterior-ring polygons;
- low, medium, and high vertex-count strata;
- deterministic parameter variation within each generator;
- multiple split groups per family and stratum;
- a family-covered split seed with an approximately 80/10/10 group balance;
- generator version, code hash, parameters, seed, family, and stratum on every feature.

Polygon holes are excluded because the v0.4 learned decoder does not support them. Individual
geometries are capped at 512 unique vertices so the initial dense-attention encoder can consume
them.

## Audit contract

The audit verifies:

- manifest checksums and declared row counts;
- feature, vertex, geometry-type, generator-family, and split distributions;
- duplicate geometry checksums and cross-split duplicates;
- split groups assigned to more than one split;
- missing or malformed teacher scores;
- polygon holes and sequences beyond the model limit;
- candidate, review, and movement-supervision coverage.

Warnings are written into a machine-readable JSON report. Fatal checksum, manifest, leakage, or
teacher-label failures produce a non-zero CLI exit.

## First experiment

The first experiment uses a small CPU profile to prove the runtime on the development machine.
Reports must keep neural fallback separate from neural success and must materialize the teacher
ranking directly as an oracle. A standard encoder comparison is gated on that oracle being a
credible target; scaling a model cannot repair a teacher that underperforms its source baselines.

The first model is evaluated only as teacher imitation. A superiority claim requires stronger
production baselines, real held-out GIS sources, complete quality-compression curves, and human or
screen-space preference evidence.

## Real-data boundary

No third-party GIS geometry is committed by this milestone. Candidate European and North American
sources will be recorded with their authoritative license, attribution, acquisition date, CRS, and
source identifier before an importer downloads them. Generated exports, checkpoints, and reports
remain local under `.geoscalex/`.

## Implementation batches

1. Pilot and audit specification.
2. Dataset audit library and CLI with leakage tests.
3. Deterministic balanced pilot builder and CLI.
4. Configurable small training profiles and runtime smoke test.
5. Local 1,000-geometry dataset, first checkpoint, benchmark report, and documented findings.
6. Authoritative real-data shortlist for explicit source/license selection.
