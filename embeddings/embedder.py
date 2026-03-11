"""Vertex AI embedding wrapper using text-embedding-004.

Uses Google Cloud Vertex AI for embeddings — no OpenAI key required.
The same service account used for Google Drive authenticates to Vertex AI.

Task types improve retrieval quality:
  - RETRIEVAL_DOCUMENT  → used when embedding document chunks at ingestion time
  - RETRIEVAL_QUERY     → used when embedding the user's query at retrieval time

Batches requests in groups of 100 and retries on transient errors
using exponential backoff via tenacity.
"""

import logging
from typing import Literal

import vertexai
from google.oauth2 import service_account
from tenacity import retry, stop_after_attempt, wait_exponential
from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

from config.settings import get_settings

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100
_VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY", "SEMANTIC_SIMILARITY"]


def _init_vertexai() -> None:
    """Initialise Vertex AI with project, location, and service account credentials."""
    settings = get_settings()
    credentials = service_account.Credentials.from_service_account_file(
        settings.google_service_account_json_path,
        scopes=_VERTEX_SCOPES,
    )
    vertexai.init(
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
        credentials=credentials,
    )


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _embed_batch(
    model: TextEmbeddingModel, batch: list[str], task_type: TaskType
) -> list[list[float]]:
    """Embed a single batch of texts with retry logic.

    Args:
        model: Vertex AI TextEmbeddingModel instance.
        batch: List of text strings (max 100 per Vertex AI limit).
        task_type: Vertex AI task type for optimised retrieval.

    Returns:
        List of embedding vectors in the same order as `batch`.
    """
    inputs = [TextEmbeddingInput(text, task_type) for text in batch]
    results = model.get_embeddings(inputs)
    return [r.values for r in results]


def _embed_with_task(texts: list[str], task_type: TaskType) -> list[list[float]]:
    """Core embedding logic shared by embed() and embed_query().

    Args:
        texts: List of text strings to embed.
        task_type: Vertex AI task type hint.

    Returns:
        List of float vectors in the same order as `texts`.
    """
    if not texts:
        return []

    _init_vertexai()
    settings = get_settings()
    model = TextEmbeddingModel.from_pretrained(settings.vertex_embedding_model)
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        logger.debug(
            "Embedding batch %d/%d (%d texts, task=%s)",
            i // _BATCH_SIZE + 1,
            -(-len(texts) // _BATCH_SIZE),
            len(batch),
            task_type,
        )
        all_embeddings.extend(_embed_batch(model, batch, task_type))

    logger.info(
        "Embedded %d texts via Vertex AI (%s, task=%s)",
        len(texts),
        settings.vertex_embedding_model,
        task_type,
    )
    return all_embeddings


def embed(texts: list[str]) -> list[list[float]]:
    """Embed document chunks for ingestion (RETRIEVAL_DOCUMENT task).

    Use this function when storing document vectors in Pinecone.

    Args:
        texts: List of document text strings to embed.

    Returns:
        List of 768-dim float vectors.
    """
    return _embed_with_task(texts, "RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    """Embed a single query string for retrieval (RETRIEVAL_QUERY task).

    Use this function when embedding a user's question before searching Pinecone.

    Args:
        text: The user's query string.

    Returns:
        A single 768-dim float vector.
    """
    return _embed_with_task([text], "RETRIEVAL_QUERY")[0]
