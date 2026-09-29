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
  --output .geoscalex/checkpoints/remove-move-v1.pt
uv run geoscalex-evaluate .geoscalex/exports/<dataset-id>/v1 \
  .geoscalex/checkpoints/remove-move-v1.pt \
  --output .geoscalex/reports/remove-move-v1.json
```

Set `GEOSCALEX_ENCODER_CHECKPOINT` to the checkpoint path and restart the API and worker. The
`encoder-remove-move` option then appears in the same matched-budget comparison UI as the
classical and DeepSeek methods. Training is CPU-first by default; `--device cuda` is available
when the installed PyTorch build and hardware support it.

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
[pilot benchmark v0.5 contract](docs/pilot-benchmark-v0.5.md), and the
[research proposal](adaptive-neural-gis-generalization.md).
