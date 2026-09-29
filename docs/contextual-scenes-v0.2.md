# Contextual Scenes v0.2

GeoScaleX v0.2 extends the feature-centric Dataset Lab with contextual cartographic scenes. A
scene is the unit used to decide whether a generalization is visually acceptable in its actual
surroundings. Existing features, revisions, candidates, annotations, and dataset versions remain
valid; scenes add a layer above them rather than replacing them.

## Pilot geography

The initial corpus targets Europe and North America without hard-coding particular countries or
providers. Europe is the primary discovery region because dense, irregular transport networks,
river systems, and administrative boundaries expose contextual conflicts quickly. North America
is the validation region, adding regular urban grids, long corridors, and large rural geometries.

Every scene records a broad region, a free-form locality label, and source provenance. This allows
later sampling and evaluation by continent, country, basin, metro area, source, or license while
keeping synthetic and user-provided data first-class.

## Scene contract

A scene belongs to one dataset and contains:

- exactly one target feature whose current revision is generalized;
- zero or more context features with a role: `sibling`, `parent`, `child`, `background`, or
  `obstacle`;
- region and locality metadata;
- CRS, viewport bounds, zoom, and scale denominator;
- a portable cartographic style object;
- provenance including source, license, acquisition date, and a leakage-safe location group.

Memberships also carry importance, draw order, and optional style overrides. A scene intentionally
references features rather than copying their geometry. Publication resolves every membership to
an immutable revision, so editing remains convenient while exported training versions remain
reproducible.

## Review contract

A scene review evaluates two candidates for the target revision and records:

- preference: A, B, equal, or artifact;
- acceptability: acceptable, unacceptable, or unsure;
- zero or more controlled failure tags;
- the effective viewport and an optional comment.

The initial failure vocabulary is:

- topology failure;
- visual collision;
- excessive detail loss;
- characteristic-shape loss;
- context inconsistency;
- displacement needed.

Reviews are append-only. Repeating a review creates another observation instead of mutating a
prior label.

## User workflow

1. Import, draw, or generate features as in v0.1.
2. Open Scenes and choose a target feature.
3. Add context features, assign roles, and configure region, locality, scale, viewport, and style.
4. Open the scene comparison. Context remains visible behind both matched target candidates.
5. Record preference, acceptability, failure tags, and comments.
6. Publish an immutable dataset version.

The first implementation supports manual scene composition because it makes the data contract and
quality controls observable. Automated geographic scene extraction can then target this stable
contract instead of inventing an incompatible representation.

## Export format

Dataset publication advances to schema version 2 and adds:

- `scenes.parquet`: scene metadata, target revision, split group, and split;
- `scene_members.parquet`: member roles, resolved revision IDs, importance, draw order, and style;
- `scene_reviews.parquet`: contextual preferences, acceptability, tags, viewport, and comments.

The existing `features.parquet`, `candidates.parquet`, and `annotations.parquet` remain unchanged.
All files are checksummed in the manifest. Scenes use their provenance `location_group` when
present, otherwise the target batch, so overlapping geographic samples cannot leak between
train, validation, and test splits.

## Implementation batches

1. Scene domain models, persistence, migration, validation, and API.
2. Schema-v2 Parquet publication and integrity tests.
3. Scene builder, contextual comparison, and rich review controls.
4. Browser-level workflow verification and responsive polish.

## Deferred from v0.2

- Direct downloads from third-party providers and source-specific licensing automation.
- GeoPackage and FlatGeobuf import.
- Spatial-index-based bulk scene extraction.
- Model inference and training orchestration.
- Hosted collaboration, authentication, and cloud storage.

These are deliberately deferred until the Europe/North America pilot establishes which scene
fields, sampling rules, and review signals are actually useful.
