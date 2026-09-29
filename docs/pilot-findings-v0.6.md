# Quality-Selected Supervision Findings v0.6

## Scope

This experiment changes supervision while holding the synthetic dataset, split, smoke encoder,
seed, CPU thread count, and evaluation budgets fixed. It tests whether choosing the better complete
DP or VW hierarchy per geometry is a stronger bootstrap target than averaging their ranks.

The model still receives isolated synthetic lines and polygons, has no scene context, and has no
accepted movement supervision. Results concern vertex removal only.

## Teacher ceiling

On the 114-feature test split, the quality selector chose Douglas–Peucker for 102 geometries and
Visvalingam–Whyatt for 12. It chose DP for 723 and VW for 74 of the 797 training geometries.

| Oracle or baseline | Normalized Hausdorff ↓ | Polygon IoU ↑ |
| --- | ---: | ---: |
| Quality-selected teacher | 0.02200 | 0.94656 |
| Douglas–Peucker | 0.02242 | 0.94528 |
| Visvalingam–Whyatt | 0.02707 | 0.94530 |
| v0.5 consensus teacher | 0.03959 | 0.91937 |

The selected teacher is 1.9% better than DP and 18.7% better than VW on mean normalized Hausdorff
distance. Unlike the consensus target, it is therefore a credible bootstrap ceiling. Selection is
per geometry across four budgets, so it can be slightly worse than DP at an individual budget even
while being better over the complete curve.

## Controlled encoder results

| Checkpoint | Target and objective | Normalized Hausdorff ↓ | Polygon IoU ↑ |
| --- | --- | ---: | ---: |
| v0.5, 10 epochs | consensus + rank regression | 0.05892 | 0.86547 |
| v0.5, 30 epochs | consensus + rank regression | 0.05847 | 0.86628 |
| v0.6, 10 epochs | quality-selected + rank regression | 0.05783 | 0.87797 |
| v0.6, 10 epochs | quality-selected + weighted hybrid | 0.05798 | 0.87524 |
| v0.6, up to 30 epochs | quality-selected + rank regression | **0.05265** | **0.87758** |

The primary v0.6 run stopped after 26 epochs and restored epoch 21, whose validation loss was
0.01511. Relative to the best v0.5 checkpoint, normalized Hausdorff error improved by 10.0% and
polygon IoU improved by 0.0113. All 456 candidates were valid and satisfied the requested budget;
fallback remained 0.44%.

The first experiment that replaced regression with strongly weighted listwise/top-k/boundary terms
regressed. A later hybrid kept regression as the anchor and nearly matched it, but did not beat it.
Rank regression therefore remains the default while the hybrid stays available as an explicit
ablation.

## Remaining gap

The encoder's mean top-k agreement with the selected teacher was 67.5%. Agreement was 42.3% at 10%
retention, 56.1% at 25%, 78.6% at 50%, and 93.1% at 75%. The aggressive budgets remain the main
failure mode.

The encoder still lost paired Hausdorff comparisons to DP in 95.2% of cases and to VW in 77.9%.
Its mean error remains 0.03023 above DP, and polygon IoU remains 0.06770 below DP. The improvement
validates the supervision repair but does not establish competitiveness.

## Decision

The next iteration should focus on the imitation gap at low budgets rather than increasing model
width immediately:

1. report top-k agreement and geometry quality by budget in every experiment;
2. test cutoff-weighted regression or sampled pairwise losses concentrated near the 10% and 25%
   boundaries;
3. add human preference and edited movement targets through the existing review workflow;
4. add the first geographically held-out real-data slice;
5. compare a larger encoder only after a small-model objective improves aggressive-budget recall.

The local PyTorch checkpoint remains the inference path. Ollama and other external models may
generate review candidates, but are neither required nor treated as ground truth.
