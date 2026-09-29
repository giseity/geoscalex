# GeoScaleX

GeoScaleX is a local-first dataset and evaluation lab for adaptive neural GIS generalization.

## Prerequisites

- Node.js 22+
- pnpm 10+
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Development

```bash
cp .env.example .env
pnpm install
uv sync
pnpm dev
```

Open <http://127.0.0.1:5173>. The API is available at
<http://127.0.0.1:8000/api/v1/health>.

Local state is stored under `.geoscalex/` and is intentionally ignored by Git.

## Neural simplification experiment

The classical methods and DeepSeek probe work without PyTorch. Install the optional ML dependencies
only when training or running the purpose-built encoder:

```bash
uv sync --extra ml
uv run geoscalex-train .geoscalex/exports/<dataset-id>/v1 \
  --output .geoscalex/checkpoints/remove-move-v1.pt \
  --profile smoke
uv run geoscalex-evaluate .geoscalex/exports/<dataset-id>/v1 \
  .geoscalex/checkpoints/remove-move-v1.pt \
  --output .geoscalex/reports/remove-move-v1.json
```

Set `GEOSCALEX_ENCODER_CHECKPOINT` to the checkpoint path and restart the API and worker. The
`encoder-remove-move` option then appears in the same matched-budget comparison UI as the
classical and DeepSeek methods. The project pins the optional dependency to PyTorch's CPU index for
reproducible development on this machine. `--device cuda` remains supported by the code; preparing
a CUDA environment requires changing the explicit `pytorch-cpu` source to a compatible CUDA index
and regenerating the lockfile.

Create and audit a deterministic synthetic pilot before training:

```bash
uv run geoscalex-pilot --count 1000 --output .geoscalex/pilot-v1.json
uv run geoscalex-audit .geoscalex/exports/<dataset-id>/v1
uv run geoscalex-experiment .geoscalex/exports/<dataset-id>/v1 \
  .geoscalex/experiments/pilot-smoke-v1 --profile smoke --epochs 10
```

The `smoke` model profile validates the pipeline on a CPU. Use `--profile standard` for the
larger baseline encoder after the pilot has passed its audit.

## Checks

```bash
pnpm check
pnpm test
pnpm build
```

See [the Dataset Lab architecture](docs/dataset-lab-v0.1.md), the
[contextual scenes v0.2 contract](docs/contextual-scenes-v0.2.md), the
[automated scene extraction v0.3 contract](docs/automated-scene-extraction-v0.3.md), the
[budgeted neural simplification v0.4 contract](docs/budgeted-neural-simplification-v0.4.md), the
[pilot benchmark v0.5 contract](docs/pilot-benchmark-v0.5.md), the
[real-data source shortlist](docs/real-data-sources-v0.5.md), and the
[research proposal](adaptive-neural-gis-generalization.md).
