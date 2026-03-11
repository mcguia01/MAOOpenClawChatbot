"""Application settings loaded from environment variables / .env file.

All configuration lives here. No module should hardcode credentials or
magic values — import `get_settings()` instead.

Authentication strategy
-----------------------
A single Google service account JSON file (GOOGLE_SERVICE_ACCOUNT_JSON_PATH)
provides credentials for all Google services:
  - Google Drive (document listing + download)
  - Vertex AI embeddings (text-embedding-004)
  - Vertex AI Vector Search (upsert, query, delete)
  - Vertex AI Claude (AnthropicVertex — Claude on GCP)
No OpenAI, Pinecone, or direct Anthropic API keys are required.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings.

    All fields map 1:1 to variables in .env.example.
    Required fields raise a ValidationError on startup if missing.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Google Cloud — shared auth ────────────────────────────────────────────
    google_cloud_project: str = Field(..., description="GCP project ID for Vertex AI billing")
    google_service_account_json_path: str = Field(
        "./secrets/service_account.json",
        description="Path to GCP service account JSON — used for Drive, embeddings, Vector Search, and Claude",
    )

    # ── Vertex AI — Embeddings ────────────────────────────────────────────────
    google_cloud_location: str = Field(
        "us-central1",
        description="Vertex AI region for text-embedding-004 and Vector Search (us-central1 recommended)",
    )
    vertex_embedding_model: str = Field(
        "text-embedding-004",
        description="Vertex AI embedding model name",
    )

    # ── Vertex AI — Vector Search ─────────────────────────────────────────────
    vertex_vector_search_index_id: str = Field(
        ..., description="Numeric ID of the Vertex AI Vector Search index (from setup script)"
    )
    vertex_vector_search_endpoint_id: str = Field(
        ..., description="Numeric ID of the Vertex AI Vector Search index endpoint (from setup script)"
    )
    vertex_vector_search_deployed_index_id: str = Field(
        "openclaw_mao",
        description="String ID used when deploying the index to the endpoint",
    )
    vector_metadata_db_path: str = Field(
        "./data/chunks.db",
        description="Local SQLite path for chunk text/metadata (upgrade to Firestore for multi-instance)",
    )

    # ── Vertex AI — Claude (AnthropicVertex) ─────────────────────────────────
    vertex_claude_region: str = Field(
        "us-east5",
        description="GCP region where Anthropic Claude is available on Vertex AI",
    )
    vertex_claude_model: str = Field(
        "claude-sonnet-4-5@20250514",
        description="Claude model ID on Vertex AI (format: <model>@<YYYYMMDD>)",
    )

    # ── Google Drive ──────────────────────────────────────────────────────────
    google_drive_folder_id: str = Field(..., description="ID of the Google Drive source folder")

    # ── Microsoft Teams / Bot Framework ──────────────────────────────────────
    microsoft_app_id: str = Field("", alias="MicrosoftAppId", description="Teams bot App ID")
    microsoft_app_password: str = Field(
        "", alias="MicrosoftAppPassword", description="Teams bot App Password"
    )
    bot_port: int = Field(3978, description="Port for the aiohttp bot server")

    # ── RAG ───────────────────────────────────────────────────────────────────
    top_k_chunks: int = Field(5, description="Number of context chunks to retrieve")
    chunk_size: int = Field(500, description="Max characters per chunk")
    chunk_overlap: int = Field(50, description="Character overlap between consecutive chunks")
    retrieval_score_threshold: float = Field(
        0.75,
        description="Minimum similarity score to include a chunk (dot product = cosine sim for unit vectors)",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton.

    Raises:
        pydantic.ValidationError: if required env vars are missing or invalid.
    """
    return Settings()
