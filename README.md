# OpenClaw — MAO Process Document Chatbot

OpenClaw is a RAG-based chatbot that lets consulting employees query Manhattan Active Omni (MAO)
process documents and SOPs stored in Google Drive. It is exposed via Microsoft Teams using the
Bot Framework SDK and powered by Anthropic Claude on Google Cloud Vertex AI.

**All AI services run through Google Cloud** — a single service account provides access to
Google Drive, Vertex AI embeddings (`text-embedding-004`), and Claude via `AnthropicVertex`.
No OpenAI or direct Anthropic API keys are required.

---

## Architecture

```
Google Drive (.docx / .pptx / .xlsx)
        │  (service account auth)
        ▼
┌──────────────────────┐
│  ingestion/pipeline  │  fetch → parse → chunk → embed → upsert
└──────────────────────┘
        │                         ┌─────────────────────────────┐
        │  Vertex AI              │  Vertex AI text-embedding-004│
        │  (text-embedding-004)   │  768-dim vectors             │
        ▼                         └─────────────────────────────┘
┌──────────────────────────┐      ┌─────────────────────────────────────┐
│  Vertex AI Vector Search │◄────►│  rag/ (retrieve + answer)           │
│  + SQLite metadata sidecar│     │  Claude via AnthropicVertex (Vertex) │
└──────────────────────────┘      └─────────────────────────────────────┘
                                         │
                                         ▼
                          ┌─────────────────────────────┐
                          │  bot/  (Teams Bot Framework) │
                          │  aiohttp POST /api/messages  │
                          └─────────────────────────────┘
                                         │
                                         ▼
                                 Microsoft Teams
```

---

## Setup

```bash
# 1. Clone and create virtualenv
git clone <repo-url>
cd openclaw
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and fill in GOOGLE_CLOUD_PROJECT, GOOGLE_DRIVE_FOLDER_ID, etc.

# 4. Place Google service account JSON
#    The service account needs roles: Drive Reader, Vertex AI User, Service Account Token Creator
mkdir secrets
cp /path/to/service_account.json secrets/service_account.json

# 5. Create Vertex AI Vector Search index (ONE-TIME — takes 10–30 minutes)
python scripts/setup_vertex_index.py
# Copy the printed VERTEX_VECTOR_SEARCH_INDEX_ID and VERTEX_VECTOR_SEARCH_ENDPOINT_ID into .env

# 6. Ingest documents from Google Drive
python -m ingestion.pipeline

# 7. Run the Teams bot
python -m bot.app
```

---

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID for Vertex AI billing | Yes |
| `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` | Path to GCP service account JSON | No (default: `./secrets/service_account.json`) |
| `GOOGLE_DRIVE_FOLDER_ID` | ID of the Google Drive folder containing docs | Yes |
| `GOOGLE_CLOUD_LOCATION` | Vertex AI region for embeddings | No (default: `us-central1`) |
| `VERTEX_EMBEDDING_MODEL` | Vertex AI embedding model name | No (default: `text-embedding-004`) |
| `VERTEX_CLAUDE_REGION` | GCP region for Claude on Vertex AI | No (default: `us-east5`) |
| `VERTEX_CLAUDE_MODEL` | Claude model ID on Vertex AI (`model@YYYYMMDD`) | No (default: `claude-sonnet-4-5@20250514`) |
| `VERTEX_VECTOR_SEARCH_INDEX_ID` | Numeric ID of the Vertex AI Vector Search index (from setup script) | Yes |
| `VERTEX_VECTOR_SEARCH_ENDPOINT_ID` | Numeric ID of the Vertex AI Vector Search endpoint (from setup script) | Yes |
| `VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID` | String ID set when deploying the index to the endpoint | No (default: `openclaw_mao`) |
| `VECTOR_METADATA_DB_PATH` | Local SQLite path for chunk text/metadata | No (default: `./data/chunks.db`) |
| `MicrosoftAppId` | Teams bot App ID from Azure Bot registration | Yes |
| `MicrosoftAppPassword` | Teams bot App Password | Yes |
| `BOT_PORT` | Port for the aiohttp bot server | No (default: 3978) |
| `TOP_K_CHUNKS` | Number of context chunks to retrieve | No (default: 5) |
| `CHUNK_SIZE` | Characters per chunk | No (default: 500) |
| `CHUNK_OVERLAP` | Overlap between consecutive chunks | No (default: 50) |
| `RETRIEVAL_SCORE_THRESHOLD` | Minimum dot-product similarity score (cosine sim for unit vectors) | No (default: 0.75) |

### GCP Service Account Required Roles

| Role | Purpose |
|---|---|
| `roles/drive.reader` (Drive API scope) | List and download Drive files |
| `roles/aiplatform.user` | Call Vertex AI embedding API |
| `roles/iam.serviceAccountTokenCreator` | Generate tokens for AnthropicVertex auth |

---

## Adding New Documents

1. Drop the new `.docx`, `.pptx`, or `.xlsx` file into the configured Google Drive folder.
2. Run the ingestion pipeline:
   ```bash
   python -m ingestion.pipeline
   ```
3. Alternatively, the nightly scheduler automatically re-syncs at 2:00 AM UTC.

---

## Running Tests

```bash
pytest -v --tb=short
```

All tests use mocked external dependencies (no real API calls).
