# Real-Data Pilot Findings v0.7

GeoScaleX v0.7 completes the first end-to-end real-data pass. The result validates the platform
workflow, but it does not validate the current encoder as a better generalizer: the synthetic-only
checkpoint transfers poorly to the small Seattle holdout.

## Source and import

The pilot uses the official U.S. Census Bureau TIGERweb 2026 services. The service identifies the
data as Census Bureau material and supports GeoJSON queries. Census technical documentation states
that U.S. Government works are not eligible for copyright protection under 17 U.S.C. section 105
and requests source attribution.

- [TIGERweb REST service directory](https://tigerweb.geo.census.gov/tigerwebmain/TIGERweb_restmapservice.html)
- [Transportation service](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer)
- [Hydrography service](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Hydro/MapServer)
- [TIGER/Line legal and citation documentation](https://www2.census.gov/geo/pdfs/maps-data/data/tiger/tgrshp2022/TGRSHP2022_TechDoc_Ch1.pdf)

The queries cover a Seattle, Washington bounding box of `-122.42,47.55,-122.25,47.72`. Secondary
roads came from Transportation layer 6. Areal hydrography came from Hydro layer 1 with a
`0.00001`-degree maximum allowable offset and six-digit geometry precision to keep the pilot
tractable. The exact query URLs, acquisition date, license declaration, layer, source checksum, and
derived semantic properties are recorded in batch provenance.

| Measure | Result |
| --- | ---: |
| Submitted/imported features | 75 / 75 |
| Lines / polygons | 50 / 25 |
| Invalid geometries | 0 |
| Encoder-eligible geometries | 70 (93.3%) |
| Train / validation / test | 66 / 5 / 4 |
| Cross-split groups or duplicate leakage | 0 / 0 |
| Within-export duplicate geometry rows | 10 |
| Vertex median / p95 / maximum | 20 / 572.7 / 2,045 |

The audit passed with no fatal findings. The duplicate warning is preserved rather than silently
deduplicated because the source contains distinct records with identical geometry. The test split
is only four features, so its numbers are a smoke signal, not a statistically useful benchmark.

## Review queue

The v0.6 checkpoint scored all eligible features at 10% and 25% retention. Five features were
skipped because they contain interior rings or exceed 512 model vertices. The 20 highest-priority
targets produced 19 contextual scenes; one target had no context within the configured radius.
Every created scene records top-k disagreement, normalized Hausdorff quality gap, ratio-level
components, teacher choice, fallback state, and checkpoint SHA-256.

The highest priority was `1.0967`. The top items include water polygons such as Haller Lake and
Salmon Bay Waterway, plus State Route 522. This is consistent with a real domain gap rather than a
queue dominated by random low-complexity features.

## Held-out benchmark

The existing synthetic-trained rank-regression checkpoint was evaluated without retraining.

| Method | Normalized Hausdorff ↓ | Polygon IoU ↑ | Mean latency |
| --- | ---: | ---: | ---: |
| Encoder remove-and-move | 0.03474 | 0.91257 | 27.41 ms |
| Quality-selected teacher oracle | 0.00837 | 0.96055 | 15.14 ms* |
| Douglas–Peucker | 0.00889 | 0.96182 | 31.02 ms |
| Visvalingam–Whyatt | 0.01406 | 0.97204 | 18.35 ms |

`*` Teacher timing reconstructs precomputed labels and is not a fair inference benchmark.

The encoder remained 100% valid and budget-exact, but used fallback for 25% of candidates. It lost
all 16 Hausdorff comparisons to Douglas–Peucker, and against Visvalingam–Whyatt it lost 75% and tied
25%. At 10% retention its normalized Hausdorff error was `0.06636`; polygon IoU was `0.79194`.

This is the most important v0.7 result: the current model has learned useful synthetic rankings,
but those rankings do not yet transfer reliably to real road and water geometry.

## Cutoff-weighted objective

A controlled 30-epoch smoke experiment changed only the objective. Rank regression remains the
default.

| Objective | Overall HD ↓ | Overall IoU ↑ | 10% HD ↓ | 25% HD ↓ |
| --- | ---: | ---: | ---: | ---: |
| Rank regression | **0.05265** | **0.87758** | **0.13848** | 0.04431 |
| Cutoff weighted | 0.05554 | 0.86960 | 0.14751 | **0.04362** |

Cutoff weighting slightly improved 25% geometry quality and 10% top-k agreement, but degraded the
10% geometry result and the aggregate. It is useful as an opt-in ablation, not as the new default.

## Decision

v0.7 establishes the real-data loop and exposes the domain gap. The next useful work is human
review of the 19 prioritized scenes, followed by a second North American locality to enlarge the
held-out groups and mixed synthetic/real training. Model scaling would be premature before those
labels exist. A later import pass should also decide whether identical source geometries should be
grouped, deduplicated, or retained as semantically distinct records.
