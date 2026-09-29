# Automated Scene Extraction v0.3

GeoScaleX v0.3 turns an imported or generated feature corpus into contextual scenes in bulk. It
operates on features already present in a dataset; downloading third-party geography remains an
ingestion concern so licensing, attribution, and provider-specific behavior do not leak into the
scene contract.

## Product outcome

A researcher can select a batch or the whole dataset, preview the extraction coverage, queue a
reproducible background run, inspect the inferred roles, and continue directly into contextual
comparison and review. Manual scene composition remains available for exceptional or deliberately
designed cases.

## Extraction contract

An extraction request records:

- dataset and optional target batch;
- pilot region, locality, location-group prefix, scale, and style preset;
- neighborhood radius and maximum context members;
- optional target geometry types and maximum scene count;
- whether targets that already have an active scene should be skipped.

Geographic `EPSG:4326` geometries use metres for search and distance ranking through a projected
analysis representation. Local geometries use their native coordinate units. Features with an
incompatible coordinate space or CRS are not mixed into a scene.

The engine builds one spatial index per compatible coordinate group. For each target it queries
the configured neighborhood and ranks context deterministically by spatial relation, distance,
and stable feature ID. Roles are inferred with these deliberately simple rules:

1. a covering polygon is a `parent`;
2. a feature covered by a polygon target is a `child`;
3. a crossing or intersecting feature is an `obstacle`;
4. a nearby feature with the same geometry kind or semantic class is a `sibling`;
5. other nearby features are `background`.

Every inferred member stores its relation, distance, and engine decision in scene style metadata.
The scene provenance stores the full configuration, engine version, target revision checksum,
and a stable extraction fingerprint. Re-running the same configuration therefore produces the
same ordering and can safely skip existing targets.

## Preview and job lifecycle

`POST /scene-extractions/preview` performs no writes. It returns eligible, incompatible, existing,
and isolated-target counts plus a bounded sample of proposed scenes and inferred role totals.

`POST /scene-extractions` queues a cancellable `scene-extraction` job. The local worker rebuilds
the same plan from current immutable revisions, creates scenes incrementally, reports progress,
and returns created scene IDs and aggregate skip counts. Cancellation keeps already-created scenes
valid and reports partial completion.

The Scenes workspace presents extraction controls, preview statistics, the latest runs, and links
from completed results into the generated scene cards.

## Quality and safety rules

- Extraction never edits, archives, or duplicates source features.
- Existing active scene targets are skipped by default.
- Archived features are never targets or context.
- Context is capped per scene and ordered deterministically.
- Isolated targets are reported rather than emitted as empty scenes.
- Preview and execution share the same planner to prevent configuration drift.
- Manual review remains authoritative; inferred roles are proposals, not labels of truth.

## Implementation batches

1. Extraction specification and reproducibility contract.
2. Spatial planner, request models, preview API, worker execution, and focused tests.
3. Scene-workspace controls, preview summary, run monitoring, and result integration.
4. End-to-end browser verification, release checks, and v0.3 version marker.

## Deferred beyond v0.3

- Direct OSM, Overture, Natural Earth, or national-provider downloads.
- GeoPackage and FlatGeobuf ingestion.
- Learned role classification or cartographic conflict scoring.
- Joint multi-target extraction, displacement, and topology repair.
- Server-side PostGIS indexes for hosted multi-user deployments.
