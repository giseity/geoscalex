# Real-data Source Shortlist v0.5

Reviewed on 2026-09-29. This registry records candidates only and is not legal advice. No
third-party geometry has been downloaded or added to a GeoScaleX dataset.

## Recommendation

Start the first real-data pilot in North America with a small US region rather than mixing sources
and licences immediately:

1. use USGS 3D Hydrography Program data for watercourse lines and waterbody polygons;
2. add a bounded selection of Census TIGER/Line features after checking the selected archive's
   metadata and terms;
3. reserve a neighbouring geographic area, not random features from the same extract, for the
   final test split;
4. use Natural Earth only as an external small-scale reference, not as raw training geometry.

This path supplies both target geometry types, keeps provenance understandable, and avoids making
the first checkpoint depend on share-alike or non-commercial terms. Europe should follow as a
separate domain-transfer experiment once the OSM or national-source licensing strategy is chosen.

## Candidates

| Source | Coverage and role | Terms observed | Decision |
| --- | --- | --- | --- |
| [USGS 3DHP](https://www.usgs.gov/3d-hydrography-program/access-3dhp-data-products) | Current U.S. hydrography; line and polygon training/evaluation | USGS says it moved from maintained NHD products to 3DHP in 2024. [USGS licensing guidance](https://www.usgs.gov/data-management/data-licensing) explains public-domain U.S. government work and the use of CC0 where needed; dataset metadata must still be retained. | **Preferred first source.** Download one current, bounded work unit only after recording its release/DOI and licence metadata. |
| [Census TIGER/Line](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) | U.S. roads, hydrography, boundaries, and other line/polygon classes | Published by the U.S. Census Bureau with annual technical documentation. The selected archive's metadata and website notices must be captured before ingestion; do not infer terms merely from the absence of a licence file. | **Preferred complement**, pending an archive-specific metadata check. Its [cartographic boundary files](https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html) are useful external simplified references, not automatic labels. |
| [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/) | Global vectors at 1:10m, 1:50m, and 1:110m | The project states its raster and vector data are public domain. The geometry is already heavily generalized. | **Validation/reference only.** Useful for scale-level comparisons and domain transfer; unsuitable as the sole source of high-resolution originals. |
| [OpenStreetMap](https://osmfoundation.org/wiki/Licence_and_Legal_FAQ) | Broad European and North American roads, waterways, boundaries, and land-use polygons | ODbL 1.0 permits commercial use but requires attribution and share-alike for qualifying derivative databases. [OSMF's attribution guidance](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines#Machine_learning_models) specifically addresses machine-learning models: substantial OSM training extracts are derivative databases that must be available under ODbL when publicly used, and trained models require attribution in expected documentation. | **High-value, deferred decision.** Use only after defining how training exports, provenance, model cards, and any public derivative database will satisfy ODbL. |
| [Eurostat GISCO](https://ec.europa.eu/eurostat/en/web/gisco/geodata) | European administrative/statistical geometry and selected transport data | Terms vary by dataset. The administrative-unit page grants use subject to attribution and explicitly excludes commercial use; other pages refer back to general and dataset-specific provisions. | **Research/reference only by default.** Do not mix GISCO administrative units into a commercially reusable training corpus without a separate licence decision. |

## Ingestion gate

Before an importer fetches any real source, its source record must contain:

- authoritative landing page and direct artifact URL;
- provider, release/vintage, acquisition timestamp, and source identifier or DOI;
- licence or public-domain statement URL, required attribution, and redistribution conditions;
- original CRS, target metric CRS, geographic bounds, and geometry classes selected;
- archive checksum and importer version;
- geographic grouping rule used to prevent spatial leakage;
- whether the source is an original, a teacher/reference generalization, or evaluation-only data.

The first import should be deliberately small enough for visual inspection. Expanding geographic
coverage before the audit, benchmark, and review loop work on one region would only make failures
more expensive to diagnose.
