# Claude Code Prompt — MAO OpenClaw Chatbot (Greenfield Scaffold)

## Context

You are scaffolding a production-ready Python project called **OpenClaw** — a RAG-based chatbot for consulting employees to query a repository of Manhattan Active Omni (MAO) process documents and SOPs. Documents are stored in Google Drive in `.pptx`, `.xlsx`, and `.docx` formats. The bot is exposed via Microsoft Teams using the Bot Framework SDK.

---

## Task

Create a complete greenfield project structure from scratch with all files, configs, and placeholder implementations. Do not leave any file empty — every module should have working skeleton code with clear `TODO` comments where credentials or business logic need to be filled in.

---

## Project Structure to Create

```
openclaw/
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml
│
├── ingestion/
│   ├── __init__.py
│   ├── drive_client.py         # Google Drive API auth + file listing
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── docx_parser.py      # python-docx text + table extraction
│   │   ├── pptx_parser.py      # python-pptx slide text + notes extraction
│   │   └── xlsx_parser.py      # openpyxl sheet/row extraction as structured text
│   ├── chunker.py              # LangChain text splitter, 500 token chunks / 50 overlap
│   └── pipeline.py             # Orchestrates: fetch → parse → chunk → embed → upsert
│
├── embeddings/
│   ├── __init__.py
│   ├── embedder.py             # OpenAI text-embedding-3-small wrapper
│   └── vector_store.py         # Pinecone init, upsert, query, delete-by-filename
│
├── rag/
│   ├── __init__.py
│   ├── retriever.py            # Similarity search against Pinecone, returns top-K chunks
│   ├── prompt_builder.py       # Assembles system prompt + context chunks + user query
│   └── chain.py                # LangChain ConversationalRetrievalChain using Claude
│
├── bot/
│   ├── __init__.py
│   ├── app.py                  # Bot Framework app entry point (aiohttp server)
│   ├── bot_handler.py          # ActivityHandler — routes messages to RAG pipeline
│   └── formatter.py            # Formats RAG response + source citations for Teams cards
│
├── scheduler/
│   ├── __init__.py
│   └── sync_job.py             # Nightly re-sync: delete stale vectors, re-ingest Drive folder
│
├── config/
│   ├── __init__.py
│   └── settings.py             # Pydantic BaseSettings — loads all env vars with validation
│
└── tests/
    ├── __init__.py
    ├── test_parsers.py
    ├── test_chunker.py
    ├── test_retriever.py
    └── test_bot_handler.py
```

---

## File-by-File Instructions

### `README.md`
Include:
- Project overview (MAO OpenClaw, what it does, who it's for)
- Architecture diagram in ASCII or Mermaid
- Setup instructions: clone → create venv → install requirements → set .env → run ingestion → run bot
- Environment variables table (name, description, required/optional)
- How to add new documents (drop in Google Drive folder, run sync)
- How to run tests

---

### `.env.example`
Include all required environment variables with placeholder values and inline comments:

```
# Anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key

# OpenAI (embeddings only)
OPENAI_API_KEY=your-openai-api-key

# Pinecone
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=us-east-1-aws
PINECONE_INDEX_NAME=openclaw-mao

# Google Drive
GOOGLE_DRIVE_FOLDER_ID=your-folder-id
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=./secrets/service_account.json

# Microsoft Teams Bot Framework
MicrosoftAppId=your-teams-app-id
MicrosoftAppPassword=your-teams-app-password
BOT_PORT=3978

# RAG Settings
TOP_K_CHUNKS=5
CHUNK_SIZE=500
CHUNK_OVERLAP=50
```

---

### `.gitignore`
Standard Python gitignore. Also ignore:
- `.env`
- `secrets/`
- `*.json` in root (service account files)
- `__pycache__`
- `.pytest_cache`
- `dist/`, `build/`, `.eggs/`

---

### `requirements.txt`
Include pinned or minimum versions for:
- `anthropic`
- `openai`
- `pinecone-client`
- `langchain`
- `langchain-community`
- `langchain-anthropic`
- `google-api-python-client`
- `google-auth`
- `google-auth-oauthlib`
- `python-docx`
- `python-pptx`
- `openpyxl`
- `botbuilder-core`
- `botbuilder-schema`
- `botbuilder-integration-aiohttp`
- `aiohttp`
- `pydantic`
- `pydantic-settings`
- `python-dotenv`
- `apscheduler`
- `pytest`
- `pytest-asyncio`

---

### `config/settings.py`
Use `pydantic-settings` `BaseSettings`. All fields map 1:1 to `.env.example`. Include type hints, default values where safe, and a `model_config` with `env_file=".env"`.

---

### `ingestion/drive_client.py`
- Authenticate using a Google service account JSON file
- Method: `list_files(folder_id) -> List[dict]` — returns file metadata (id, name, mimeType, modifiedTime)
- Method: `download_file(file_id, dest_path) -> Path` — downloads to a temp directory
- Support `.docx`, `.pptx`, `.xlsx` MIME types only; skip others with a log warning
- Include a `TODO` comment for adding Drive Push Notifications as an upgrade path

---

### `ingestion/parsers/docx_parser.py`
- Function: `parse(file_path: Path) -> List[dict]`
- Extract paragraphs as text chunks
- Extract tables — convert each row to a pipe-delimited string
- Each returned dict: `{ "text": str, "source": filename, "section": heading or "table", "page": None }`

---

### `ingestion/parsers/pptx_parser.py`
- Function: `parse(file_path: Path) -> List[dict]`
- Extract text from all shapes on each slide
- Extract speaker notes if present
- Each returned dict: `{ "text": str, "source": filename, "section": f"Slide {n}: {slide_title}", "page": slide_number }`

---

### `ingestion/parsers/xlsx_parser.py`
- Function: `parse(file_path: Path) -> List[dict]`
- Iterate over all sheets
- Treat first row as header; each subsequent row becomes a text block: `"Header1: val | Header2: val | ..."`
- Each returned dict: `{ "text": str, "source": filename, "section": sheet_name, "page": row_number }`
- Add a `TODO` for handling merged cells edge case

---

### `ingestion/chunker.py`
- Use LangChain `RecursiveCharacterTextSplitter`
- Chunk size and overlap loaded from `settings`
- Function: `chunk(parsed_items: List[dict]) -> List[dict]`
- Preserve all metadata fields from the input dicts on each resulting chunk
- Add a `chunk_id` field: `f"{source}_{section}_{index}"`

---

### `ingestion/pipeline.py`
- Function: `run_ingestion(folder_id: str)` — full pipeline orchestration
- Steps: list Drive files → download each → parse by extension → chunk → embed → upsert to Pinecone
- Log each step (use Python `logging`, not `print`)
- On error for a single file: log and continue (don't abort the whole run)
- After upsert: delete temp downloaded files

---

### `embeddings/embedder.py`
- Wrap OpenAI `text-embedding-3-small`
- Function: `embed(texts: List[str]) -> List[List[float]]`
- Batch calls in groups of 100 to stay within API limits
- Include retry logic with exponential backoff (use `tenacity`)

---

### `embeddings/vector_store.py`
- Initialize Pinecone client from settings
- Function: `upsert_chunks(chunks: List[dict])` — embeds and upserts with metadata
- Function: `query(query_text: str, top_k: int) -> List[dict]` — returns chunks with scores
- Function: `delete_by_source(source_filename: str)` — deletes all vectors for a file by metadata filter
- Pinecone vector ID format: `chunk_id` from chunker

---

### `rag/retriever.py`
- Function: `retrieve(query: str, top_k: int) -> List[dict]`
- Calls `vector_store.query()`
- Filters out any chunks below a score threshold (default 0.75, configurable in settings)
- Returns list of chunk dicts with `text`, `source`, `section`, `score`

---

### `rag/prompt_builder.py`
Build the full prompt passed to Claude. Include:

**System prompt content:**
```
You are OpenClaw, an expert assistant for Manhattan Active Omni (MAO) consulting processes.
You answer questions exclusively based on the provided document context.
Always cite the source document and section for every claim you make.
If the answer is not found in the provided context, respond with:
"I couldn't find information about that in the MAO document repository. 
Please check with your project lead or review the source documents directly."
Never fabricate MAO-specific process details, configuration steps, or SOP instructions.
```

- Function: `build_prompt(query: str, chunks: List[dict], chat_history: List[dict]) -> List[dict]`
- Returns a messages array compatible with the Anthropic API
- Includes chat history for multi-turn support
- Formats context as numbered source blocks: `[1] Source: filename | Section: section\n{text}`

---

### `rag/chain.py`
- Function: `ask(query: str, chat_history: List[dict]) -> dict`
- Calls `retriever.retrieve()` → `prompt_builder.build_prompt()` → Anthropic Claude API
- Returns `{ "answer": str, "sources": List[dict] }`
- Use `claude-sonnet-4-20250514` model, `max_tokens=1500`
- If no chunks retrieved above threshold → return fallback message without calling Claude

---

### `bot/app.py`
- `aiohttp` web app entry point
- Register Bot Framework `CloudAdapter`
- Single POST route: `/api/messages`
- Load `MicrosoftAppId` and `MicrosoftAppPassword` from settings
- Start server on `BOT_PORT`
- Include `if __name__ == "__main__"` block

---

### `bot/bot_handler.py`
- Extend `ActivityHandler`
- `on_message_activity`: extract user text → call `rag.chain.ask()` → send reply via `formatter`
- Maintain per-conversation chat history using `turn_context.activity.conversation.id` as key (in-memory dict for now)
- Add a `TODO` for replacing in-memory history with Azure Cosmos DB or Redis

---

### `bot/formatter.py`
- Function: `format_response(answer: str, sources: List[dict]) -> Activity`
- Format as a Teams `HeroCard` or plain message with:
  - Answer text
  - "Sources" section listing each unique filename + section
- Function: `format_error() -> Activity` — generic error message card

---

### `scheduler/sync_job.py`
- Use `APScheduler` `BackgroundScheduler`
- Schedule `ingestion.pipeline.run_ingestion()` nightly at 2:00 AM
- Function: `start_scheduler()` — called from `bot/app.py` on startup
- Log start/end of each sync run with file counts

---

### `tests/`
- `test_parsers.py` — unit tests for each parser using small fixture files (create minimal fixture `.docx`, `.pptx`, `.xlsx` inline or as base64 strings)
- `test_chunker.py` — test chunk size, overlap, metadata preservation
- `test_retriever.py` — mock Pinecone, test score threshold filtering
- `test_bot_handler.py` — mock `ask()`, test message routing and history tracking

---

## Additional Instructions for Claude Code

1. **No empty files.** Every `.py` file must have at least a working skeleton with imports, class/function signatures, docstrings, and `TODO` comments.
2. **Use type hints everywhere.**
3. **Use Python `logging`** module throughout — no bare `print()` statements.
4. **All secrets come from `config/settings.py`** — no hardcoded values anywhere.
5. **`pyproject.toml`** should define project metadata and point to `requirements.txt`.
6. After creating all files, run `pip install -r requirements.txt --dry-run` to validate the package list resolves without conflicts. If there are conflicts, fix `requirements.txt`.
7. Print a summary of all files created and their line counts when done.

---

## Success Criteria

When complete, a developer should be able to:
1. Clone the repo
2. Copy `.env.example` → `.env` and fill in credentials
3. Run `python -m ingestion.pipeline` to ingest documents from Google Drive
4. Run `python -m bot.app` to start the Teams bot
5. Message the bot in Teams and receive a cited MAO process answer
