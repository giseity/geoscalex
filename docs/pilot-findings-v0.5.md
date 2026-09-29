# Synthetic Pilot Findings v0.5

## Scope

This is a pipeline and teacher-imitation baseline, not a claim that the neural encoder outperforms
classical generalization. The dataset is entirely synthetic, contains no contextual scenes, and has
no accepted human-reviewed movement targets. Consequently, this run evaluates learned vertex
ranking; the movement head remains effectively inactive.

## Dataset

The balanced `synthetic-pilot-v1` export contains 1,000 valid, model-eligible geometries and
169,020 vertices:

- 500 lines across five generator families and 500 polygons across three families;
- 797 train, 89 validation, and 114 group-isolated test features;
- 54 lines and 60 polygons in the test split;
- low, medium, and high vertex strata, with 24 minimum, 129 median, and 480 maximum vertices;
- no invalid geometries, duplicate rows, cross-split duplicates, or leaking split groups;
- manifest SHA-256 `b262767993403d7e64207f2947c12709f6e8990e7b92f0e1212d889b67e6c4b5`.

The split seed requested by the recipe was `90210`; the builder selected `91173` as the first
nearby seed satisfying both generator-family coverage and the group-balance tolerance.

## Runtime and model

The experiments ran under WSL2 on an Intel Core i7-8650U allocation exposing three physical
cores, six logical CPUs, and 11 GiB RAM. PyTorch `2.7.1+cpu` used three intra-op threads.

The `smoke` encoder has 27,075 trainable parameters: two Transformer layers, hidden width 32, four
attention heads, feed-forward width 128, and dropout 0.05. It was trained with batch size 16,
AdamW, learning rate 0.001, seed 4812, and early-stopping patience 5. The initial 10-epoch run was
extended to 30 epochs because validation loss had not plateaued.

```bash
uv run geoscalex-experiment \
  .geoscalex/exports/05152f1c-63b3-4e55-967d-efd8f591c2fe/v1 \
  .geoscalex/experiments/pilot-smoke-v1 \
  --profile smoke --epochs 10 --threads 3

uv run geoscalex-experiment \
  .geoscalex/exports/05152f1c-63b3-4e55-967d-efd8f591c2fe/v1 \
  .geoscalex/experiments/pilot-smoke-30-v1 \
  --profile smoke --epochs 30 --threads 3
```

## Results

All methods produced valid geometries and satisfied the exact requested budget for all 456 test
cases: 114 geometries at retention ratios 0.10, 0.25, 0.50, and 0.75.

| Method | Normalized Hausdorff ↓ | Polygon IoU ↑ | Mean latency | p95 latency | Fallback |
| --- | ---: | ---: | ---: | ---: | ---: |
| Encoder, 10 epochs | 0.05892 | 0.86547 | 12.20 ms | 32.39 ms | 0.44% |
| Encoder, 30 epochs | 0.05847 | 0.86628 | 12.13 ms | 32.70 ms | 0.66% |
| Douglas–Peucker | 0.02242 | 0.94528 | 16.07 ms | 56.29 ms | 0% |
| Visvalingam–Whyatt | 0.02707 | 0.94530 | 10.51 ms | 29.39 ms | 0% |
| Teacher-consensus oracle | 0.03959 | 0.91937 | not comparable | not comparable | 0% |

The 30-epoch checkpoint is the primary result. Its validation loss fell from 0.02799 at epoch 1 to
0.01539 at epoch 10 and 0.01201 at epoch 30. That additional 22% loss reduction after epoch 10
improved normalized Hausdorff error by only 0.8% and polygon IoU by 0.00081. It therefore did not
materially change geometric quality.

In paired comparisons, the 30-epoch encoder lost on normalized Hausdorff distance to
Douglas–Peucker in 95.6% of cases and to Visvalingam–Whyatt in 75.4%. It beat them in 2.9% and
21.1% of cases, respectively. The largest gap was at 10% retention. Polygon IoU was also lower by
0.079 on average against both baselines.

The teacher-consensus oracle reconstructs geometry directly from the precomputed target ranks,
without encoder prediction. It lost to Douglas–Peucker in 88.8% of paired Hausdorff comparisons.
Against Visvalingam–Whyatt it won 36.8%, tied 12.7%, and lost 50.4%; its mean error remained 0.01253
higher. This means the current average-of-ranks target has a lower quality ceiling than either
classical source on this benchmark. Teacher timing measures reconstruction from precomputed labels
and is intentionally excluded from latency comparisons.

The 30-epoch run took 367.7 seconds to train and 18.4 seconds to evaluate. Encoder cold start was
24.7 ms. The latency table is useful only for this Python CPU pipeline: neural inference is
single-sample, classical implementations are not production-native libraries, and batching has not
yet been benchmarked.

## Decision

Do not scale the present loss and averaged-rank labels into the `standard` encoder yet. The oracle
shows that a larger model could imitate the target more accurately and still remain worse than the
baselines. The next training iteration should:

1. preserve DP and VW teacher proposals separately instead of averaging their ranks;
2. select or score proposals using direct geometry and, later, contextual visual objectives;
3. train importance with a ranking or top-k-aware loss at sampled budgets rather than only scalar
   Smooth L1 regression;
4. keep the oracle in every report so target quality and imitation error stay distinguishable;
5. add a geographically held-out real-data slice before making quality claims;
6. benchmark batched inference separately from end-to-end candidate validation.

The lack of accepted reviewed movement candidates is a separate limitation. These checkpoints
learned removal order only; zero-offset behavior is expected.

## Interpretation boundary

The group-isolated test split contains the same synthetic generator families as training, so it
measures within-family generalization rather than out-of-distribution behavior. The findings do not
measure cartographic appearance, sibling-feature relationships, viewport context, topology across
features, or production throughput. Credible superiority evidence still requires geographically
held-out real data, stronger production baselines, complete quality-compression curves, human
preference judgements in styled context, and accepted movement supervision.
