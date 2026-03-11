"""Retriever — queries Pinecone and filters results by similarity score.

Only chunks with a score >= RETRIEVAL_SCORE_THRESHOLD (from settings)
are returned to the caller. Chunks below the threshold are silently
discarded, and the chain will return a fallback message when the result
list is empty.
"""

import logging
from typing import Any

from config.settings import get_settings
from embeddings.vector_store import query as vector_query

logger = logging.getLogger(__name__)


def retrieve(query: str, top_k: int | None = None) -> list[dict[str, Any]]:
    """Retrieve relevant document chunks for the given query.

    Args:
        query: Natural language question from the user.
        top_k: Maximum number of chunks to fetch before threshold filtering.
               Defaults to settings.top_k_chunks.

    Returns:
        List of chunk dicts (text, source, section, score) that meet the
        score threshold. May be empty if no relevant chunks are found.
    """
    settings = get_settings()
    k = top_k or settings.top_k_chunks
    threshold = settings.retrieval_score_threshold

    raw_results = vector_query(query_text=query, top_k=k)

    filtered = [r for r in raw_results if r.get("score", 0.0) >= threshold]

    logger.info(
        "Retriever: %d/%d chunks passed score threshold %.2f for query: %.80s",
        len(filtered),
        len(raw_results),
        threshold,
        query,
    )
    return filtered
