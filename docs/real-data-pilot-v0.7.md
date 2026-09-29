# Real-Data Pilot v0.7

GeoScaleX v0.7 moves the research loop from synthetic-only experiments to reproducible local
imports and targeted human review. It extends the existing GeoJSON importer and contextual scene
workflow rather than introducing a separate data path.

## Outcome

A researcher can load a GeoJSON or JSON FeatureCollection, declare its CRS and source provenance,
explode supported multi-geometries, assign leakage-safe geographic groups, deterministically cap a
large file, and inspect every rejection. Imported features can immediately enter the existing scene
extraction, comparison, editing, review, publication, training, and evaluation workflow.

## Import contract

The importer accepts LineString, Polygon, MultiLineString, and MultiPolygon input. Multi-geometries
are exploded into independently identified parts when enabled. Geometry collections and unsupported
types are rejected explicitly.

Each batch records:

- a canonical SHA-256 checksum of the submitted FeatureCollection;
- source name, URI, license, acquisition date, file name, and optional user provenance;
- coordinate space and CRS;
- requested and imported counts, sampling seed, and import schema version;
- split-group strategy and grid size.

Every imported revision records its original feature index, optional source identifier, part index,
and `split_group`. A configured source property supplies the group when present; otherwise the
geometry centroid is assigned to a deterministic grid cell. Nearby features therefore remain in
the same train, validation, or test split after publication.

Deterministic sampling hashes the import seed, source identifier, part index, and normalized
geometry. Selecting the lowest hashes makes the same capped import reproducible without depending
on input order.

## Review-batch contract

The existing scene extractor remains responsible for spatial context. A review-priority stage will
score eligible targets at 10% and 25% retention using the configured checkpoint and the
quality-selected teacher. Low top-k agreement and large geometry-quality gaps receive higher
priority. The generated scenes retain the score components and checkpoint hash in provenance.

Reviewers compare classical and encoder candidates, mark acceptability and failure tags, and edit
only valuable failures. External LLM or Ollama candidates may be added later, but are optional and
never become ground truth without review.

## Model experiment

The first real-data experiment keeps rank regression as the control and adds a cutoff-weighted
variant that emphasizes vertices near the teacher boundary, especially at 10% and 25% retention.
Synthetic and geographically held-out real results remain separate in reports.

## Boundaries

The initial file path is JSON/GeoJSON rather than GeoPackage or FlatGeobuf, avoiding an immediate
GDAL dependency. Imported data remains local under the existing database and export directories.
Source licenses must be verified before acquisition; the platform records declarations but cannot
decide whether a dataset is legally suitable for training.

## Implementation batches

1. Specification.
2. Provenance-rich deterministic importer and API tests.
3. Import UI controls and rejection/provenance summary.
4. Uncertainty-prioritized contextual review batches.
5. Cutoff-weighted training objective and focused tests.
6. First held-out North American import, audit, benchmark, and findings.
