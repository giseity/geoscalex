# Dataset Lab v0.1 Architecture

GeoScaleX Lab is a desktop-oriented local web application. A Vite React client talks to a
FastAPI service bound to localhost. Python owns geometry semantics, storage, generators,
classical simplification, validation, metrics, and future model execution.

## Runtime boundaries

- The browser owns presentation and transient editing state.
- SQLite owns mutable metadata and immutable revision records.
- The local filesystem owns large artifacts and published datasets.
- A separate worker process executes registered repository-controlled jobs.
- Parquet is the training interchange format; DuckDB verifies and explores exports.

Cloud services are not part of v0.1. Storage and job-running boundaries remain explicit so
filesystem/SQLite and local execution can later be replaced by object storage/PostgreSQL and
container workers.

## Repository shape

```text
apps/web/                 Vite, React, TypeScript, and shadcn UI
src/geoscalex/api/        FastAPI transport and request validation
src/geoscalex/storage/    SQLite models, migrations, and repositories
src/geoscalex/geometry/   validation, metrics, and simplification hierarchies
src/geoscalex/generators/ deterministic synthetic-geometry registry
src/geoscalex/worker/     cancellable background job runner
src/geoscalex/datasets/   immutable Parquet publication
```

The web app and API are separate processes because geometry work belongs in Python and should
never block the browser. They are still one local product: `pnpm dev` starts the web client, API,
and worker, all bound to loopback interfaces.

## Data model and lifecycle

1. A workspace contains datasets.
2. A dataset contains batches, collections, features, annotations, and published versions.
3. A batch records the provenance shared by a generator run or import.
4. A feature points at one current immutable geometry revision. Editing creates another revision;
   it does not overwrite history.
5. A candidate is a reproducible classical simplification of a revision. It stores its algorithm,
   parameters, hierarchy scores, protected-vertex mask, geometry, and metrics.
6. An annotation compares candidate A and B in a recorded viewport and stores `A`, `B`, `equal`,
   or `artifact`.
7. Publication snapshots current revisions into a content-checksummed Parquet dataset with stable,
   group-aware train/validation/test splits.

Geometry is stored in both GeoJSON (for the API and inspection) and WKB (for compact, unambiguous
interchange). Synthetic generators accept a recorded seed and expose Pydantic-generated parameter
schemas to the UI; arbitrary code is deliberately not accepted from the browser.

## Comparison semantics

The lab supports overlay and draggable swipe views. Candidate controls can use either a numeric
tolerance or a matched vertex budget, which makes comparisons between algorithms meaningful.
Metrics are supporting evidence—not an automatic quality label—because contextual visual quality
is precisely what the annotation workflow is intended to capture.

## Milestones and commits

The initial implementation is delivered as reviewable vertical batches:

1. workspace scaffold and architecture;
2. persistent domain model and API;
3. geometry validation and classical teacher hierarchies;
4. deterministic generators and background jobs;
5. dataset export/versioning;
6. visual dataset workbench and browser-level verification.

Each batch includes its own focused tests. The final smoke test creates a workspace and dataset,
generates samples, creates matched simplification candidates, records a preference, and publishes
an immutable dataset version.

## v0.1 constraints

- Geometry types: LineString and Polygon, including interior rings.
- Import: GeoJSON.
- Editing: immutable revisions, duplicate, archive, undo/redo, and explicit hole operations.
- Teachers: Douglas–Peucker and monotonic Visvalingam–Whyatt hierarchies.
- Comparison: swipe and overlay, matched vertex budgets, and preference labels.
- Organization: workspaces, datasets, batches, collections, generator runs, and immutable
  dataset versions.
- No authentication, cloud deployment, arbitrary browser-edited code, model training,
  MultiLineString, or MultiPolygon.
