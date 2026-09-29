# Quality-Selected Supervision v0.6

GeoScaleX v0.6 repairs the first pilot's supervision before increasing model capacity. The v0.5
teacher averaged Douglas–Peucker and Visvalingam–Whyatt ranks and produced worse geometry than
either source baseline. This milestone keeps their hierarchies separate, chooses a teacher using
direct geometry quality, and trains the encoder for ranking and exact top-k selection.

## Outcome

For every training geometry, the loader constructs the DP and VW hierarchies independently and
evaluates their zero-movement candidates at retention ratios 0.10, 0.25, 0.50, and 0.75. The
hierarchy with lower mean normalized Hausdorff distance becomes that geometry's training target.
Deterministic ties select Douglas–Peucker.

Teacher selection is per geometry rather than per budget. This preserves a nested hierarchy, so a
smaller retained set remains a subset of larger retained sets. It does not yet attempt to learn a
different vertex ordering for every viewport or budget.

## Training objective

Smooth L1 rank regression is replaced by three complementary terms:

- listwise cross-entropy preserves the complete teacher ordering;
- balanced top-k classification teaches retained versus removed vertices at sampled budgets;
- a boundary-ranking term separates the weakest retained score from the strongest removed score.

Each geometry is exposed to different deterministic budget ratios across epochs. Human-approved
movement examples retain their reviewed budget so their displacement supervision remains aligned.
The movement objective and displacement safety penalty otherwise remain unchanged.

## Evaluation contract

Reports materialize both teacher targets without encoder prediction:

- `teacher-quality-oracle` measures the selected DP-or-VW hierarchy used for v0.6 training;
- `teacher-consensus-oracle` preserves the v0.5 averaged-rank reference.

The report records teacher selection counts and paired comparisons against both classical methods.
A larger encoder profile remains gated on the small model showing that it can approach the stronger
oracle. Teacher reconstruction latency is not treated as an inference benchmark.

## Boundaries

Quality selection uses synthetic isolated geometry and normalized Hausdorff distance. It cannot
represent styled appearance, contextual preference, topology between features, or human judgement.
The selected teacher is a stronger bootstrap target, not the final product objective.

No Ollama or general-purpose language model is involved in encoder training or inference. External
models remain optional candidate generators whose output must be validated and reviewed.

## Implementation batches

1. Specification and immutable v0.5 checkpoint compatibility.
2. Separate DP, VW, consensus, and quality-selected targets in the dataset loader.
3. Listwise, top-k, and boundary-aware training losses with deterministic budget sampling.
4. Dual teacher-oracle reporting and focused tests.
5. Synthetic smoke checkpoint, matched benchmark, and findings.
