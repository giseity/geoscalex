# Adaptive Neural GIS Generalization

# 1. Project Objective

The goal is to build a learned system for **multiscale GIS geometry simplification and, eventually, feature selection**.

The initial focus is intentionally narrow:

> Given a line or polygon ring and an explicit complexity budget, predict which existing vertices
> matter and, once reviewed movement supervision is available, how retained vertices should move
> to produce a better simplified shape.

The model should learn which geometric details are visually or structurally important while allowing less important detail to disappear as the map becomes coarser.

The product thesis is not to reproduce a classical simplifier with a neural network. Classical algorithms are useful bootstrap teachers and strong baselines, but the learned system should ultimately solve a broader decision problem:

> **Given a geometry, its spatial context, its semantics, its visual style, and its rendering constraints, determine which details should remain visible.**

The expected advantages are:

- better visual quality at a fixed geometry or byte budget,
- decisions that depend on surrounding features and cartographic context,
- amortized execution of an otherwise expensive multi-objective search,
- high-throughput batched inference on parallel hardware,
- and eventually just-in-time generalization for dynamic maps.

The neural approach is successful only if it eventually provides measurable value beyond the algorithms used to initialize it.

The long-term objective is a system capable of adaptive cartographic generalization based on:

- geometry,
- scale,
- semantics,
- neighboring features,
- visual importance,
- topology,
- rendering conditions,
- and eventually viewport constraints.

The system should support two complementary operating modes:

```text
offline preprocessing
    → compute reusable multiscale hierarchies

online inference
    → adapt to a live viewport, style, dataset, or user objective
```

---

# 2. Core V1 Problem

V1 is split into two deliberately incremental capabilities:

- **V1A** predicts a hierarchical importance score for every existing vertex;
- **V1B** retains that correspondence and additionally predicts a budget-conditioned displacement
  for retained vertices.

V1B can therefore produce new coordinates without immediately taking on arbitrary output
cardinality, insertion, reordering, or unconstrained sequence generation.

Instead, the model will receive an existing geometry:

```text
v0 ─ v1 ─ v2 ─ v3 ─ v4 ─ v5
```

and assign an importance or critical-scale value to each vertex:

```text
v0     ∞
v1     2.4
v2    18.7
v3     4.1
v4    51.3
v5     ∞
```

At runtime, a threshold determines which vertices remain.

For example:

```text
Fine scale

v0 ─ v1 ─ v2 ─ v3 ─ v4 ─ v5
```

```text
Medium scale

v0 ───── v2 ─────── v4 ─ v5
```

```text
Coarse scale

v0 ──────────────── v4 ─ v5
```

Ideally, simplification remains hierarchical:

```text
coarse geometry
    ⊂
medium geometry
    ⊂
fine geometry
```

Zooming in therefore adds detail rather than replacing the geometry with a completely different approximation.

---

# 3. Why Start With Vertex Selection and Constrained Movement?

Allowing the model to directly generate replacement coordinates creates many additional problems:

- self-intersections,
- invalid polygons,
- broken topology,
- inconsistent shared boundaries,
- moving intersections,
- geometry instability between zoom levels,
- difficult supervision,
- larger output space.

Vertex scoring turns the problem into structured prediction:

```text
geometry
   ↓
model
   ↓
importance per existing vertex
```

Computational geometry can then enforce validity.

The principle for V1 is therefore:

> **Machine learning decides what is important. Deterministic geometry code decides what is valid.**

After the selection baseline is working, a displacement head can move retained vertices while a
deterministic decoder continues to enforce source order, endpoints, ring closure, budget, and
validity. This remove-and-move formulation is the first generative experiment. Fully arbitrary
coordinate generation and diffusion models remain optional later research directions.

## 3.1 Why Use a Learned Decision Model?

Classical simplifiers usually optimize a predefined geometric criterion. They are fast and reliable, but they have limited ability to combine many contextual signals or learn cartographic preference from examples.

A learned model may improve on them in three ways.

### Contextual quality

The acceptable simplification of a feature may depend on:

- sibling and parent geometries,
- higher- and lower-level features,
- nearby labels and symbols,
- feature class and semantic importance,
- line width, casing, opacity, and color,
- viewport scale and feature density,
- occlusion and visual competition.

This changes the objective from minimizing isolated geometric error to preserving the information that matters in the rendered map.

### Amortized optimization

A strong contextual classical pipeline may need to run several algorithms, explore many parameter settings, render candidates, evaluate conflicts, and select a result. A learned model can approximate the outcome of that expensive decision process in one or a small number of forward passes.

The relevant performance comparison is therefore not only:

```text
one neural pass vs one Douglas–Peucker call
```

but also:

```text
one learned decision
vs
multi-algorithm + multi-parameter + render-and-evaluate search
```

### Parallel and dynamic execution

Purpose-built models can batch many geometries or viewports and execute efficiently on GPUs and other parallel hardware. This creates a path toward high-throughput tile production and, if end-to-end latency becomes low enough, just-in-time generalization.

These benefits are hypotheses to measure rather than assumptions. Benchmarks must include preprocessing, data transfer, model inference, deterministic constraint enforcement, and output encoding.

## 3.2 Validity and Hierarchy Contract

Thresholding scalar scores guarantees nested vertex sets, but it does not by itself guarantee a valid geometry at every threshold. Polygon shortcuts may self-intersect, holes may become invalid, and independently simplified shared boundaries may diverge.

V1 must therefore define a deterministic constrained decoder. A practical approach is to compute or validate a progressive removal order and reject removals that would violate configured constraints. The resulting order must remain valid at every supported threshold.

For lines, polygons, and networks, the constraint policy should explicitly define:

- protected endpoints and junctions,
- minimum valid ring size,
- self-intersection rules,
- hole containment,
- shared-boundary handling,
- and whether rejected removals are permanently blocked or reconsidered later.

Validity enforcement is part of the measured runtime and part of the product, not an evaluation-only repair step.

---

# 4. System Overview

The project should be separated into three systems.

```text
             DATASET / GEOMETRY LAB

Real GIS ───────────────┐
                        │
Procedural generators ──┼──→ Canonical geometries
        ↑               │
    LLM-generated       │
    generator code      │
                        ↓
              Classical simplifiers
             DP / VW / Tippecanoe
                        │
                        ↓
               automatic metrics
                        │
                        ↓
              visual comparison
                        │
                        ↓
                  dataset
```

```text
                  MODEL TRAINING

              geometry + labels
                      ↓
              PyTorch encoder
                      ↓
             per-vertex scores
```

```text
                     RUNTIME

             geometry + stored scores
                      ↓
                map scale / MPP
                      ↓
                   threshold
                      ↓
              simplified geometry
```

These systems should remain loosely coupled.

---

# 5. Dataset Strategy

Training data should come from multiple sources.

## 5.1 Real GIS Data

Real geometry keeps the model grounded in actual GIS distributions.

Possible sources include:

- OpenStreetMap roads,
- rivers,
- coastlines,
- administrative boundaries,
- Natural Earth,
- public transportation networks,
- publicly available cadastral or hydrographic datasets.

The model should encounter a wide variety of:

- vertex densities,
- geometry lengths,
- curvature patterns,
- digitization quality,
- geographic scales,
- feature types.

Every imported source should retain its license, acquisition date, source identifier, CRS, geographic grouping, and preprocessing history. Geographic and source groupings must survive into dataset splits so nearby or derived geometries cannot leak across training and evaluation.

---

## 5.2 Procedural Synthetic Data

Synthetic geometry should be generated using deterministic programs rather than individual LLM-generated coordinate sequences.

Example generators:

```python
generate_meandering_river(...)
generate_noisy_coastline(...)
generate_hairpin_road(...)
generate_zigzag(...)
generate_smooth_curve_with_noise(...)
generate_bay(...)
generate_peninsula(...)
generate_polygon_with_holes(...)
```

Each generator should expose parameters and a random seed.

For example:

```text
generator = meandering_river_v2
seed = 4813

major_bends = 4
noise_amplitude = 0.03
oxbow_strength = 0.7
samples = 600
```

This makes every sample:

- deterministic,
- reproducible,
- editable,
- parameterized,
- easy to regenerate.

Generator family and version should be treated as split dimensions. Some evaluations should hold out complete generator families or parameter ranges rather than only unseen random seeds.

---

# 6. Role of an LLM such as DeepSeek

The LLM should initially function as a **dataset engineering assistant**, not as the simplification model itself.

Useful responsibilities include:

### Geometry generator authoring

Prompt:

> Create a parameterized Python generator for a coastline containing several major bays plus high-frequency digitization noise.

The LLM produces generator code.

The generated program can then create thousands of examples using different seeds and parameters.

### Scenario generation

The LLM can suggest difficult cases such as:

- hairpins,
- narrow peninsulas,
- oxbows,
- near-collinear vertices,
- small but important bends,
- noisy straight lines,
- repeated oscillations,
- near self-intersections.

### Failure-driven dataset generation

If the trained model struggles with a particular geometric pattern, the LLM can be asked to generate new procedural scenarios targeting that weakness.

This creates an iterative curriculum:

```text
model
  ↓
failure cases
  ↓
LLM generates adversarial generators
  ↓
new examples
  ↓
retraining
```

### Optional visual critic

A vision-capable model may later compare rendered simplifications.

Its output should initially be treated as a **weak preference signal**, not authoritative ground truth.

---

# 7. Geometry Lab

Before building a sophisticated model, a lightweight research environment should be created.

The Geometry Lab should support:

- loading real GIS geometries,
- running procedural geometry generators,
- editing generator code,
- adjusting generator parameters,
- running classical simplification algorithms,
- running learned models,
- visual before/after comparison,
- automatic metrics,
- human preference labeling.

A possible interface:

```text
┌──────────────────────┬────────────────────────────┐
│ Scenario             │ Generator Code             │
│                      │                            │
│ Meandering river     │ def generate(...):         │
│                      │     ...                    │
│ Seed: 184            │                            │
│                      │                  [Run]     │
├──────────────────────┴────────────────────────────┤
│                                                   │
│ ORIGINAL                 CANDIDATE                │
│                                                   │
│ ~~~~~~~~~~~~             ~~~~~~~~                 │
│                                                   │
├───────────────────────────────────────────────────┤
│ Scale           [────────●────────]               │
│                                                   │
│ Original vertices:      842                       │
│ Candidate vertices:      91                       │
│ Hausdorff error:        1.3 px                    │
│ Reduction:             89.2%                      │
│                                                   │
│ [A better] [Equal] [B better] [Artifact]         │
└───────────────────────────────────────────────────┘
```

Suggested frontend technologies:

- React,
- TypeScript,
- MapLibre GL JS,
- Monaco Editor.

Generated code should execute in an isolated or sandboxed environment.

The first Geometry Lab does not require arbitrary code editing. A read-only comparison viewer and a deterministic generator library are sufficient for the initial benchmark; embedded editing and sandboxed execution can be added when failure-driven generator authoring becomes an active workflow.

---

# 8. Classical Algorithms

Classical simplification methods remain important.

Useful baselines include:

- Douglas–Peucker,
- Visvalingam–Whyatt,
- Tippecanoe,
- potentially topology-aware simplifiers.

They serve several purposes:

```text
baseline
benchmark
initial weak supervision
comparison candidate
failure analysis
```

They should **not necessarily define ground truth**.

The long-term objective is to learn cases where cartographic importance differs from purely geometric error.

The baseline suite should include strong production-quality and topology-aware configurations, not only minimal textbook implementations. Each comparison should record algorithm parameters, runtime, memory use, output size, and validity behavior.

Classical methods play two distinct roles:

```text
bootstrap teachers for early representation learning

strong competitors that the mature system must outperform
```

Teacher imitation validates the pipeline, but it is not the final claim of the project.

---

# 9. Creating Initial Training Targets

Initially, training targets can be derived from classical simplification hierarchies.

For example, a vertex may survive:

```text
tolerance 0.1   ✓
tolerance 0.2   ✓
tolerance 0.5   ✓
tolerance 1     ✓
tolerance 2     ✓
tolerance 5     ✗
tolerance 10    ✗
```

This implies a critical scale or importance level.

Instead of storing many binary decisions:

```text
keep at scale A
keep at scale B
remove at scale C
...
```

store one continuous target:

```text
critical_scale = 3.7
```

This provides compact multiscale supervision.

Visvalingam-style effective-area values may also provide useful initial per-vertex importance labels.

The meaning and units of `critical_scale` must be fixed before dataset generation. Candidates include normalized geometric tolerance, effective area, meters per pixel, or a progressive removal rank. The stored representation must define how the value maps back from normalized model coordinates to runtime scale.

Teacher scores should describe a monotonic progressive hierarchy. In particular, local measurements taken independently at the original geometry are not always equivalent to the effective importance produced by sequential removal.

## 9.1 Moving Beyond a Single Teacher

The initial dataset should retain outputs from several teachers rather than immediately collapsing them into one label. At a given budget, different algorithms may preserve different useful structures.

A stronger supervision pipeline is:

```text
multiple algorithms and parameter settings
                ↓
       candidate geometries
                ↓
geometric + topological + screen-space evaluation
                ↓
   best candidate / Pareto set
                ↓
     preference supervision
```

This allows the model first to learn when different classical behaviors are appropriate, then to improve beyond them using human preference and contextual signals.

The longer-term feedback loop should be failure-driven:

```text
model uncertainty or failure
          ↓
targeted real or synthetic cases
          ↓
automatic metrics + selective human review
          ↓
new preference data
          ↓
retraining and reevaluation
```

This is initially an active-learning loop. Reinforcement learning may later be useful if simplification is formulated as a sequential decision process, but it is not required for the first preference-learning system.

---

# 10. Canonical Data Representation

Different representations should be used for different stages.

## 10.1 External GIS / Interchange

Use formats such as:

```text
GeoJSON
GeoParquet
FlatGeobuf
```

for:

- importing data,
- exporting data,
- debugging,
- visualization,
- MapLibre integration.

GeoJSON should not be the primary large-scale training representation.

---

## 10.2 Dataset Storage

Use:

```text
Apache Parquet / Arrow
```

for the training dataset.

A conceptual record could contain:

```text
geometry_id
geometry_type

coordinates

target_vertex_scores

source
source_dataset

generator_name
generator_version
generator_parameters
seed

semantic_class

metadata
```

Example:

```json
{
  "geometry_id": "river_01812",
  "geometry_type": "LineString",
  "source": "synthetic",
  "generator": "meandering_river_v3",
  "seed": 4812,

  "coordinates": [
    [0.12, 0.41],
    [0.18, 0.47],
    [0.26, 0.55]
  ],

  "target_scores": [
    999.0,
    4.2,
    18.7
  ]
}
```

---

# 11. Coordinate Preprocessing

Raw longitude and latitude should generally not be fed directly to the model.

Geometry should first be converted into an appropriate local representation.

Possible pipeline:

```text
source CRS
   ↓
local metric coordinates
   ↓
translate relative to centroid / first vertex
   ↓
normalize by characteristic length
   ↓
model coordinates
```

The objective is for the network to learn geometric structure rather than memorize geographic location.

Absolute geographic information can later be added explicitly if useful.

The representation must also address geometric equivalences that do not change the intended simplification. Tests and augmentation should cover:

- reversed LineStrings,
- cyclic shifts of polygon-ring starting vertices,
- duplicated closing vertices,
- rotation and reflection where appropriate,
- uniform scale changes,
- different sampling densities of the same underlying curve,
- and equivalent geometries split into different feature segments.

These invariances should be evaluated explicitly rather than left for the model to discover accidentally. Lines and polygon rings may require separate initial representations or models because endpoints, cyclic order, and validity constraints differ.

---

# 12. Vertex Features

Every vertex may initially receive features such as:

```text
x
y

dx_previous
dy_previous

dx_next
dy_next

previous_segment_length
next_segment_length

turning_angle

local_triangle_area

distance_from_start
relative_position_along_geometry

is_endpoint
```

Additional features can be added experimentally.

The model input for one geometry becomes:

```text
X.shape = [N, F]
```

where:

- `N` = number of vertices,
- `F` = feature dimension.

The V1A output is:

```text
y.shape = [N]
```

containing one predicted importance value per vertex. V1B adds:

```text
delta.shape = [N, 2]
```

containing budget-conditioned coordinate offsets. Only offsets for retained vertices participate
in reconstruction, and movement supervision is masked unless a reviewed candidate provides a
trusted source-to-output correspondence.

---

# 13. Batch Representation

Geometries have different numbers of vertices.

A training batch may therefore contain:

```text
geometry A:   83 vertices
geometry B:  251 vertices
geometry C:   47 vertices
```

They can initially be padded:

```text
A  [v v v v v v PAD PAD PAD]
B  [v v v v v v v   v   v  ]
C  [v v v PAD PAD PAD PAD PAD]
```

with a corresponding mask:

```text
A  [1 1 1 1 1 1 0 0 0]
B  [1 1 1 1 1 1 1 1 1]
C  [1 1 1 0 0 0 0 0 0]
```

Typical PyTorch tensors:

```text
vertex_features   [B, Nmax, F]

attention_mask    [B, Nmax]

targets           [B, Nmax]
```

More efficient variable-length or packed representations can be explored later if needed.

---

# 14. Initial Model Architecture

The first model should intentionally remain small.

Recommended architecture:

```text
vertex feature vector
        ↓
Linear projection
        ↓
Bidirectional Transformer encoder
        ↓
Bidirectional Transformer encoder
        ↓
Bidirectional Transformer encoder
        ↓
shared vertex representation
        ├─→ per-vertex importance / critical scale
        └─→ budget-conditioned displacement (dx, dy)
```

An initial configuration might use approximately:

```text
3–6 Transformer layers

hidden dimension:
128–256

attention heads:
4–8
```

The total model may only require a few million parameters.

The model does not need to be LLM-scale. Diffusion and Diffusion Transformer variants should not
be added until a direct remove-and-move baseline demonstrates a concrete need for multimodal
candidate sampling.

The Transformer is a hypothesis, not a requirement. It should be compared with simpler models such as feature-based regressors, small multilayer networks, and one-dimensional convolutional sequence models. These ablations reveal whether useful importance is mostly local or truly benefits from long-range context.

Full self-attention has quadratic cost in the number of vertices. For long coastlines, dense networks, or multi-feature scenes, later models may require:

- local or sparse attention,
- hierarchical geometry encoders,
- length-aware batching,
- spatial tiling with overlap,
- graph message passing,
- or cached per-feature embeddings.

Context-aware versions should separate reusable geometry encoding from dynamic scene conditioning where possible:

```text
per-feature geometry encoder ──┐
                              ├─→ contextual decision model
neighbor / scene encoder ─────┤
style + viewport features ────┘
```

This separation may allow base geometry embeddings to be cached while viewport-dependent decisions remain dynamic.

---

# 15. Framework

The recommended implementation stack is:

```text
PyTorch
```

for the main model.

PyTorch provides enough flexibility for:

- custom vertex features,
- masking,
- custom losses,
- variable-length geometry,
- later topology-aware operations.

Hugging Face Transformers is not necessary for V1.

Later, when the model begins representing relationships between multiple features, intersections, networks, or shared boundaries, consider:

```text
PyTorch Geometric
```

for graph-based processing.

---

# 16. Initial Training Objective

V1 can initially use supervised regression against teacher-derived critical-scale values.

For example:

\[
L_{\text{vertex}}
=
\frac{1}{N}
\sum_i
\ell(\hat{s}_i,s_i)
\]

where:

- \(s_i\) is the target vertex importance,
- \(\hat{s}_i\) is the model prediction.

Possible losses include:

```text
MSE
Huber loss
ranking loss
```

A ranking loss may eventually be particularly useful because the relative ordering of vertices may matter more than exact numerical values.

Because importance values may span several orders of magnitude, regression should also test log-transformed or otherwise calibrated targets. A combined objective may be more appropriate than pure MSE:

\[
L
=
\lambda_r L_{\text{regression}}
+
\lambda_o L_{\text{ranking}}
+
\lambda_k L_{\text{keep/remove at sampled scales}}
\]

Later phases can add a preference objective over complete candidate geometries or rendered views. Hard validity constraints should normally remain in deterministic decoding rather than being represented only as soft loss penalties.

---

# 17. Evaluation

The model should be evaluated at multiple levels.

## Vertex-Level

Measure:

```text
importance regression error
ranking correlation
keep/remove accuracy at selected scales
```

## Geometry-Level

Measure:

```text
vertex reduction
Hausdorff distance
Fréchet distance
length difference
area difference
self-intersections
topological validity
```

## Screen-Space

Render original and simplified geometry at known scale.

Measure errors in pixels rather than only world coordinates.

For dynamic inference, also measure stability under small changes in zoom, pan, viewport, and style. A visually good isolated result may still be unacceptable if nearby frames flicker or unexpectedly exchange details.

## Human Evaluation

Use the Geometry Lab to compare:

```text
classical algorithm
vs
model
```

and record:

```text
A better
B better
equivalent
artifact
```

## Matched-Budget Comparison

Methods must be compared under equivalent constraints, for example:

- equal retained vertex count,
- equal encoded byte size,
- equal maximum screen-space error,
- and identical validity requirements.

Evaluation should report quality–compression curves rather than only a few hand-selected thresholds. A method that keeps more vertices should not be declared visually superior without accounting for the additional budget.

## Generalization Splits

Random geometry-level splits are insufficient when examples share a generator, source region, or digitization style. Evaluation should hold out entire:

- geographic regions,
- source datasets,
- procedural generator families,
- semantic classes where appropriate,
- sampling-density ranges,
- and later, styles and viewport conditions.

Here, **cartographic generalization** and **machine-learning generalization to unseen data** are separate properties and both must be measured.

## Performance

Measure end-to-end behavior at several geometry lengths and batch sizes:

```text
preprocessing
+ host/device transfer
+ model inference
+ deterministic constraint enforcement
+ output encoding
```

Report throughput, median latency, tail latency, peak memory, and output storage. The classical comparison should include both a single simplifier and any stronger multi-candidate pipeline that the model is intended to amortize.

Benchmarks should state hardware, numerical precision, sequence-length distribution, batch size, warm-up policy, and whether caches are warm. Where practical, compare against optimized parallel classical implementations as well as common CPU production paths.

---

# 18. Human and Vision Preference Data

Preference records should be stored independently from base geometry records.

Example:

```json
{
  "experiment_id": "exp_8412",

  "geometry_id": "river_01812",

  "view": {
    "meters_per_pixel": 8.2,
    "width": 1440,
    "height": 900
  },

  "candidate_a": "visvalingam",
  "candidate_b": "model_v0.3",

  "metrics": {
    "a_vertices": 74,
    "b_vertices": 61,
    "a_error_px": 1.37,
    "b_error_px": 1.51
  },

  "vlm_preference": "B",
  "human_preference": "B",

  "artifact": false
}
```

This preference dataset can later become substantially more valuable than simple classical teacher labels.

---

# 19. Dataset Scale

The first experiment does not require an enormous dataset.

Recommended progression:

```text
1k geometries
5k
10k
20k
50k
100k+
```

The objective is to observe the validation scaling curve.

A reasonable first milestone is:

```text
10,000–20,000 geometries

~1–3 million vertices
```

A more serious V1 dataset might eventually contain:

```text
50,000–200,000 geometries

10–50 million labeled vertices
```

Dataset diversity is more important than raw example count.

---

# 20. Runtime Representation

After inference, each geometry can store something approximately like:

```text
x
y
critical_scale
```

per vertex.

Example:

```text
vertex     x        y        critical_scale

0          ...      ...       ∞
1          ...      ...       3.4
2          ...      ...      71.2
3          ...      ...       8.1
```

Then runtime simplification becomes:

```text
current scale
      ↓
derive threshold
      ↓
keep vertices above threshold
```

The ML model therefore does not necessarily need to execute every time the map zoom changes.

This representation may also reduce the need to maintain separate source geometries for every scale. Conventional multizoom pipelines can duplicate related geometry across zoom levels and tiles, especially when features cross tile boundaries. A base geometry plus a compact importance hierarchy can instead derive multiple levels of detail when needed.

This is a potential storage advantage, but it should not be described as inherently exponential. Total storage depends on the number of zoom levels, tile coverage, clipping and duplication behavior, feature density, compression, and caching policy. The project should measure:

```text
base geometry + importance scores
vs
materialized generalized geometries
vs
complete encoded tile pyramids
```

Encoded tile caches may still be desirable for popular static maps. Hierarchical source storage and cached delivery tiles solve different parts of the system.

For dynamic maps, the runtime path can instead be:

```text
visible geometry + scene context + style + viewport
                         ↓
               batched model inference
                         ↓
              constrained simplification
                         ↓
                 rendering / encoding
```

---

# 21. Screen Resolution and Viewport

For V1, screen dimensions should probably **not** be part of the neural model input.

The model should first attempt to predict a reusable, geometry-dependent importance hierarchy.

Runtime conditions such as:

```text
meters per pixel
zoom
device pixel ratio
style
```

can determine the threshold applied to those scores.

This separates:

```text
intrinsic geometry importance
```

from:

```text
current rendering requirements
```

This separation is a useful V1 approximation, not a claim that importance is universally intrinsic. The same bend may deserve different treatment when it represents a major road, a minor stream, or a boundary hidden underneath a thick symbol.

Viewport dimensions become substantially more important later when solving **feature selection**, because the number and density of simultaneously visible objects matter.

They may also improve vertex simplification once the model is explicitly trained for contextual rendering quality.

## 21.1 Real-Time Execution Targets

“Real time” should be defined with concrete service targets. Different products may require different budgets:

```text
interactive viewport update     tens of milliseconds
dynamic server-side tile        tens to hundreds of milliseconds
offline tile production         maximum sustained throughput
```

Exact targets should be selected from the intended deployment rather than assumed in advance. GPU batching is expected to help throughput, but interactive latency may use small batches and must include scheduling and transfer overhead.

The performance program should determine where each mode wins:

```text
static and frequently requested  → precompute and cache
dynamic but reusable geometry    → cache embeddings or hierarchies
viewport/style-specific output   → just-in-time contextual inference
```

---

# 22. Development Roadmap

## Phase 0 — Geometry Lab

Build the dataset and evaluation platform.

Implement:

- real GIS import,
- procedural generators,
- generator code editor,
- classical simplifiers,
- before/after map visualization,
- metrics,
- experiment storage.

Initial milestone:

> Generate and automatically validate 10,000 diverse geometries and their simplification hierarchies, then visually inspect a stratified sample and metric outliers.

---

## Phase 1 — Learned Vertex Hierarchy

Train the first PyTorch model.

```text
geometry
   ↓
bidirectional Transformer
   ↓
critical-scale score per vertex
```

Goal:

> Demonstrate that a compact neural network can learn useful multiscale vertex hierarchies on unseen geometry while remaining consistent under reversal, ring rotation, scale changes, and resampling.

This phase validates the representation, training pipeline, constrained decoder, and runtime path. Teacher imitation is a bootstrap milestone rather than evidence that the neural approach is already superior.

---

## Phase 2 — Better Supervision

Compare:

```text
model
Douglas–Peucker
Visvalingam
Tippecanoe
topology-aware baselines
```

in the visual evaluator.

Collect:

- best-of-teacher and Pareto candidate sets,
- human preferences,
- failure cases,
- optional VLM judgments.

Focus annotation effort on cases where methods disagree.

Goal:

> Outperform each individual classical baseline on held-out data at matched vertex or byte budgets, first by selecting and combining useful teacher behavior and then through preference learning.

---

## Phase 3 — Learned Cartographic Preference

Use the collected preference data to move beyond classical geometric simplification.

Train toward:

> Preserve perceptually meaningful structure while removing visually irrelevant detail.

Use uncertainty and observed failures to drive targeted data generation and selective human review.

---

## Phase 4 — Semantic Context

Introduce attributes such as:

```text
road class
river class
boundary type
feature importance
```

Allow the same geometry to simplify differently depending on what it represents.

---

## Phase 5 — Spatial Relationships and Topology

Represent relationships such as:

```text
road ↔ road
river ↔ river
polygon ↔ polygon
intersection
shared boundary
containment
```

Potentially introduce:

```text
PyTorch Geometric
graph neural networks
graph Transformers
```

---

## Phase 6 — Performance and Dynamic Inference

Optimize and benchmark:

```text
geometry-length bucketing
GPU batching
sparse or local attention
cached geometry embeddings
constrained decoding
tile and viewport scheduling
```

Compare end-to-end latency and throughput against both individual classical methods and multi-candidate contextual pipelines.

Goal:

> Identify the workloads where precomputation, cached hierarchies, or just-in-time inference provide the best quality, latency, throughput, and storage tradeoff.

---

## Phase 7 — Feature Selection

Move from:

```text
which vertices survive?
```

to:

```text
which complete features survive?
```

Inputs may now include:

```text
viewport
feature density
map style
screen dimensions
semantic hierarchy
rendering budget
```

---

## Phase 8 — Controlled Geometry Redrawing

Only after vertex-selection models are well understood should the system potentially predict:

```text
keep / remove
+
small coordinate displacement
```

or generate alternative generalized geometries.

This phase introduces much stricter topology and validity requirements.

---

# 23. Immediate Implementation Target

The first concrete implementation goal should be:

> **Build a reproducible and automatically validated dataset of 10,000 geometries where every vertex has one or more teacher-derived multiscale importance values, and provide an interactive viewer for inspecting those values and comparing methods at matched budgets.**

That milestone validates:

- the geometry representation,
- synthetic generators,
- preprocessing,
- classical baselines,
- storage format,
- visualization,
- definition of the target variable.

It should also produce the first reproducible benchmark covering:

- quality–compression curves,
- validity at every evaluated threshold,
- invariance and resampling consistency,
- held-out generator and geographic splits,
- end-to-end CPU and GPU performance,
- and storage for importance hierarchies versus materialized scale levels.

Only once this looks convincing should substantial model training begin.

---

# 24. Guiding Principle

The project should evolve gradually from:

```text
classical geometry
        ↓
learned imitation
        ↓
learned visual preference
        ↓
semantic cartographic generalization
        ↓
context-aware adaptive maps
```

The first research question is deliberately narrow:

> **Can a small bidirectional neural model learn a useful multiscale importance function over GIS geometry vertices?**

The larger research questions are:

> **At the same vertex or byte budget, can learned decisions produce better visual and cartographic results than strong classical baselines?**

> **Can a purpose-built model amortize contextual generalization well enough to improve production throughput or enable dynamic inference?**

> **Can one hierarchy or cached representation reduce duplicated multiscale source storage without sacrificing delivery performance?**

If the first experiment works, the same platform can answer these broader questions and support increasingly sophisticated forms of learned cartographic generalization.
