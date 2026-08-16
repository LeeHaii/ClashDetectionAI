# ClashDetectionAI

ClashDetectionAI is a chat-oriented web application for parsing Navisworks clash reports, analyzing individual clashes with a vision-language model, preserving the resulting conversation, and exporting a PDF report.

The repository is a small monorepo:

- `apps/api`: FastAPI, SQLAlchemy, report parsing, inference orchestration, SSE, and PDF rendering.
- `apps/web`: React, TypeScript, Vite, and Tailwind.
- `services/model`: model compatibility checks and production serving notes.
- `infra`: local containers and Compose configuration.
- `docs`: architecture and data-contract notes.

## Model identity

The LoRA adapter `train_2026-06-27-00-01-40` declares `Qwen/Qwen3-VL-2B-Instruct` as its base in `adapter_config.json`. The API defaults deliberately use that pair. The older `AIVision` scripts mixed this adapter with Qwen2.5-VL; the compatibility preflight rejects that mismatch.

## Local development

Copy `.env.example` to `.env`, then start each app:

```bash
cd apps/api
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

```bash
cd apps/web
pnpm install
pnpm dev
```

The default `INFERENCE_PROVIDER=mock` streams a deterministic validated response, so the complete upload/chat/PDF flow can be developed without a GPU server. Set `INFERENCE_PROVIDER=openai` to use a vLLM OpenAI-compatible endpoint.

## Docker Compose

```bash
docker compose -f infra/compose/compose.yaml up --build
```

The Compose profile starts the web and API services. Model serving is documented separately because it requires a Linux NVIDIA host and a compatibility decision from `services/model/README.md`.

## Checks

```bash
cd apps/api && pytest
cd apps/web && pnpm test && pnpm build
```

Opt-in GPU checks are never run as part of the normal test suite. See `services/model/README.md`.

