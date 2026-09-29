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

## Checks

```bash
pnpm check
pnpm test
pnpm build
```

See [the Dataset Lab architecture](docs/dataset-lab-v0.1.md), the
[contextual scenes v0.2 contract](docs/contextual-scenes-v0.2.md), and the
[research proposal](adaptive-neural-gis-generalization.md).
