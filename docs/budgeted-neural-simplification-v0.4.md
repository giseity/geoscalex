# Budgeted Neural Simplification v0.4

GeoScaleX v0.4 turns the dataset lab into an end-to-end simplification research loop. It supports
classical baselines, an optional DeepSeek candidate probe, and a small purpose-built
remove-and-move encoder under a shared matched-budget contract.

## Product outcome

A researcher can choose a line or simple exterior-ring polygon, specify either an exact retained
vertex count or a retention ratio, generate comparable candidates, review them visually, publish
the reviewed data, train the encoder, and bring a checkpoint back into the same workbench for
evaluation.

The milestone proves a reproducible pipeline. It does not claim that the initial learned model
outperforms Douglas-Peucker or Visvalingam-Whyatt.

## Budget contract

The canonical complexity budget is the number of unique output vertices. A polygon's repeated
closing coordinate is serialization, not an additional budgeted vertex. Lines therefore require
at least two vertices and polygons at least three.

Requests accept either:

- an exact `vertex-count`; or
- a `retention-ratio` in `(0, 1]`, resolved with `floor(N * ratio + 0.5)` and clamped to the valid
  range.

Every candidate records the requested budget, resolved count, achieved count, and whether the
exact budget was satisfied. Time, encoded bytes, pixel error, and scale-derived budgets remain
later extensions.

## Candidate methods

All methods share one asynchronous job and candidate contract:

- `douglas-peucker` and `visvalingam-whyatt` are deterministic local baselines;
- `deepseek-keep-move` is an optional external experimental candidate source;
- `encoder-remove-move` is the purpose-built learned model when a checkpoint is configured.

The DeepSeek probe receives normalized coordinates, geometry type, and budget only. It returns
ordered retained source indices plus coordinate offsets rather than arbitrary GeoJSON. Python
reconstructs and validates the geometry. DeepSeek output is never automatically treated as
ground truth.

## Initial learned model

The encoder consumes one target geometry at a time. Scene context is preserved in dataset exports
but is not an input to the v0.4 model. Polygon model runs accept one exterior ring and no holes.

```text
vertex features + geometry type
              -> Transformer encoder
              -> importance score per source vertex
              -> budget-conditioned displacement per source vertex
              -> exact-K constrained decoder
              -> validated geometry or recorded classical fallback
```

Importance is budget-independent so retained sets can remain hierarchical. Displacement depends
on the requested budget. The displacement head starts at zero and receives supervised movement
loss only from human-reviewed acceptable candidates that retain source-to-output correspondence.
Classical DP and VW hierarchies bootstrap the importance target.

## Validation and evaluation

The deterministic decoder protects line endpoints, preserves source order, closes polygon rings,
and validates every candidate. It progressively reduces predicted displacement before using a
clearly recorded classical fallback. Neural failures remain visible in evaluation rather than
being credited as neural successes.

Matched-budget reports include validity, budget satisfaction, Hausdorff and Frechet distance,
length and area change, polygon overlap, movement magnitude, fallback rate, and end-to-end
latency. Dataset exports retain method versions, provider/model provenance, prompt or checkpoint
hashes, token usage, validation diagnostics, and source mappings.

## Local and hosted behavior

The Vite client never receives provider credentials. A loopback TypeScript model gateway owns the
AI SDK and DeepSeek integration; FastAPI and the Python worker remain the public API, job owner,
geometry validator, and persistence authority. The gateway starts without a key and reports the
DeepSeek method unavailable. Classical workflows continue without Node AI or PyTorch extras.

## Implementation batches

1. Specification and research-proposal revision.
2. Budget semantics, candidate migration, method registry, jobs, metrics, and export schema v3.
3. Generic matched-budget comparison and review UI.
4. AI SDK model gateway and validated DeepSeek job path.
5. Dataset loader, remove-and-move encoder, training/evaluation commands, and checkpoint inference.
6. Cross-runtime tests, browser verification, documentation, and v0.4 release marker.

## Deferred beyond v0.4

- diffusion and Diffusion Transformer models;
- scene/context-conditioned training;
- polygon holes and shared-boundary topology in learned methods;
- arbitrary output vertices without source correspondence;
- byte, screen-error, time, and scale-derived hard budgets;
- long-geometry sparse attention and distributed training;
- hosted authentication and multi-user model-gateway isolation.
