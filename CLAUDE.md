# CLAUDE.md — OpenClaw Project

## Project Overview

OpenClaw is a RAG-based Teams chatbot that lets consulting employees query MAO (Manhattan Active Omni)
process documents and SOPs. Documents are stored in Google Drive (.docx, .pptx, .xlsx).
All AI services run through Google Cloud Vertex AI.

## Tech Stack

- **Python 3.11+**
- **Google Cloud Vertex AI** — `text-embedding-004` (768-dim) for embeddings, Claude via `AnthropicVertex`
- **Vertex AI Vector Search** — vector database (`DOT_PRODUCT_DISTANCE`, 768 dimensions, `STREAM_UPDATE` mode)
- **SQLite** — local metadata sidecar (`./data/chunks.db`) storing chunk text/source/section/page keyed by `chunk_id`
- **LangChain** — `RecursiveCharacterTextSplitter` for chunking only (`langchain-text-splitters`)
- **Google Drive API** — document listing and download via service account
- **Microsoft Bot Framework** — `botbuilder-core`, `botbuilder-integration-aiohttp` for Teams
- **aiohttp** — async HTTP server for the bot endpoint
- **APScheduler** — nightly Google Drive sync at 2:00 AM UTC
- **Pydantic-settings** — environment-based config with validation
- **tenacity** — exponential backoff on Vertex AI embedding calls

## Commands

```bash
# Run ingestion
python -m ingestion.pipeline

# Run the Teams bot
python -m bot.app                    # starts on http://0.0.0.0:3978

# Run tests
pytest -v --tb=short

# Code quality
black .                              # 100 char line length, Python 3.11
flake8 ingestion embeddings rag bot scheduler config tests
mypy ingestion embeddings rag bot scheduler config tests
```

## Architecture

```
Routes: bot/app.py (aiohttp POST /api/messages)
          ↓
        bot/bot_handler.py (ActivityHandler)
          ↓
        rag/chain.ask()
          ├── rag/retriever.retrieve()
          │     └── embeddings/vector_store.query()
          │           └── embeddings/embedder.embed_query()  ← Vertex AI RETRIEVAL_QUERY
          ├── rag/prompt_builder.build_prompt()
          └── AnthropicVertex (Claude on Vertex AI)

Ingestion: ingestion/pipeline.run_ingestion()
          ├── ingestion/drive_client.DriveClient
          ├── ingestion/parsers/{docx,pptx,xlsx}_parser.parse()
          ├── ingestion/chunker.chunk()
          └── embeddings/vector_store.upsert_chunks()
                └── embeddings/embedder.embed()  ← Vertex AI RETRIEVAL_DOCUMENT
```

## Key Directories

- `ingestion/` — Google Drive fetch, parse, chunk pipeline
- `ingestion/parsers/` — per-format parsers (docx, pptx, xlsx)
- `embeddings/` — Vertex AI embedder + Vertex AI Vector Search store (+ SQLite metadata)
- `rag/` — retriever, prompt builder, Claude chain
- `bot/` — aiohttp server + Bot Framework handler + formatter
- `scheduler/` — APScheduler nightly sync
- `config/` — Pydantic settings singleton
- `tests/` — pytest unit tests (all mocked, no real API calls)
- `secrets/` — gitignored; place `service_account.json` here

## Authentication

One GCP service account JSON covers all Google services:
- **Google Drive** — `drive.readonly` scope
- **Vertex AI embeddings** — `cloud-platform` scope via `vertexai.init(credentials=...)`
- **Vertex AI Vector Search** — `cloud-platform` scope via `aiplatform.init(credentials=...)`
- **Claude on Vertex** — `cloud-platform` scope via `AnthropicVertex(credentials=...)`

Required GCP roles: `roles/aiplatform.user`, `roles/iam.serviceAccountTokenCreator`

## Embedding Details

| Property | Value |
|---|---|
| Model | `text-embedding-004` |
| Dimensions | 768 |
| Ingestion task type | `RETRIEVAL_DOCUMENT` |
| Query task type | `RETRIEVAL_QUERY` |
| Batch size | 100 texts per request |
| Retry | 4 attempts, exponential backoff 2–30s |

## Claude / Vertex AI Details

- Client: `anthropic.AnthropicVertex`
- Default model: `claude-sonnet-4-5@20250514` (configurable via `VERTEX_CLAUDE_MODEL`)
- Default region: `us-east5` (configurable via `VERTEX_CLAUDE_REGION`)
- Max tokens: 1500
- Falls back to a canned message if no chunks pass the score threshold (0.75)

## Code Conventions

- **Type hints**: required on all functions
- **Logging**: `logging` module throughout — no `print()`
- **Secrets**: all from `config.settings.get_settings()` — never hardcoded
- **SQL**: parameterized queries only in SQLite metadata store (`embeddings/vector_store.py`)
- **Imports**: stdlib → third-party → local (relative within packages)
- **Naming**: snake_case functions/modules, PascalCase classes

## Configuration

All settings in `config/settings.py` via `pydantic-settings`. Required fields use `Field(...)`.
Optional fields have sensible defaults. The settings object is cached via `@lru_cache(maxsize=1)`.

Key required env vars: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_DRIVE_FOLDER_ID`, `VERTEX_VECTOR_SEARCH_INDEX_ID`, `VERTEX_VECTOR_SEARCH_ENDPOINT_ID`

## Testing Patterns

- HTTP/API calls mocked with `unittest.mock.patch`
- No real Vertex AI, Vector Search, or Teams calls in tests
- Parser tests use in-memory fixtures (python-docx, python-pptx, openpyxl)
- Bot handler tests clear `_conversation_history` in `setup_method()`
- `pytest-asyncio` with `asyncio_mode = "auto"` in `pyproject.toml`

## Important Notes

- Vertex AI Vector Search index dimension is **768** (text-embedding-004). Do NOT mix with OpenAI 1536-dim indexes.
- The index and endpoint must be created once via `python scripts/setup_vertex_index.py` (takes 10–30 min).
  Copy the printed IDs into `.env` before running ingestion.
- `DOT_PRODUCT_DISTANCE` with unit-normalised vectors equals cosine similarity ∈ [-1, 1].
  The `RETRIEVAL_SCORE_THRESHOLD=0.75` maps directly — no conversion needed.
- SQLite metadata (`./data/chunks.db`) is a local sidecar. For multi-instance deployments (Cloud Run, GKE),
  replace with Google Cloud Firestore (`google-cloud-firestore`).
- Claude model IDs on Vertex use `@YYYYMMDD` suffix format (e.g. `claude-sonnet-4-5@20250514`).
  Check Vertex AI Model Garden for the latest available versions.
- Claude on Vertex AI is only available in specific regions (currently `us-east5`).
