"""RAG chain — the main entry point for answering user questions.

Flow:
  1. Retrieve relevant chunks from Pinecone (via retriever)
  2. If no chunks pass the score threshold, return a fallback message
  3. Build the prompt (system + context + history + query)
  4. Call Anthropic Claude and return the answer + source citations
"""

import logging
from typing import Any

from anthropic import AnthropicVertex
from anthropic.types import TextBlock
from google.oauth2 import service_account

from config.settings import get_settings
from rag.prompt_builder import build_prompt, get_system_prompt
from rag.retriever import retrieve

logger = logging.getLogger(__name__)

_MAX_TOKENS = 1500
_VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

_FALLBACK_MESSAGE = (
    "I couldn't find information about that in the MAO document repository. "
    "Please check with your project lead or review the source documents directly."
)


def _get_client() -> AnthropicVertex:
    """Return a configured AnthropicVertex client using the GCP service account."""
    settings = get_settings()
    credentials = service_account.Credentials.from_service_account_file(
        settings.google_service_account_json_path,
        scopes=_VERTEX_SCOPES,
    )
    return AnthropicVertex(
        region=settings.vertex_claude_region,
        project_id=settings.google_cloud_project,
        credentials=credentials,  # type: ignore[arg-type]
    )


def ask(query: str, chat_history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Answer a user question using RAG against the MAO document repository.

    Args:
        query: The user's natural language question.
        chat_history: Optional list of prior conversation turns.
            Each turn is a dict with 'role' ('user' | 'assistant') and 'content'.

    Returns:
        Dict with keys:
          - "answer": str — Claude's response text (or fallback message)
          - "sources": list[dict] — unique source/section pairs used in context
    """
    history = chat_history or []

    # Step 1 — Retrieve context chunks
    chunks = retrieve(query)

    # Step 2 — Short-circuit if no relevant chunks found
    if not chunks:
        logger.info("No chunks above threshold for query: %.80s — returning fallback", query)
        return {"answer": _FALLBACK_MESSAGE, "sources": []}

    # Step 3 — Build prompt
    messages = build_prompt(query=query, chunks=chunks, chat_history=history)
    system_prompt = get_system_prompt()

    # Step 4 — Call Claude via Vertex AI
    settings = get_settings()
    client = _get_client()
    response = client.messages.create(
        model=settings.vertex_claude_model,
        max_tokens=_MAX_TOKENS,
        system=system_prompt,
        messages=messages,  # type: ignore[arg-type]  # list[dict] is compatible with MessageParam
    )

    first_block = response.content[0] if response.content else None
    answer = first_block.text if isinstance(first_block, TextBlock) else _FALLBACK_MESSAGE

    # Deduplicate sources
    seen: set[tuple[str, str]] = set()
    sources: list[dict[str, str]] = []
    for chunk in chunks:
        key = (chunk.get("source", ""), chunk.get("section", ""))
        if key not in seen:
            seen.add(key)
            sources.append({"source": key[0], "section": key[1]})

    logger.info(
        "ask(): answered query (%.80s) using %d chunks, %d unique sources",
        query,
        len(chunks),
        len(sources),
    )
    return {"answer": answer, "sources": sources}
