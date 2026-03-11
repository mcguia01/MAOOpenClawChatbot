"""Text chunker — splits parsed document items into fixed-size overlapping chunks.

Uses LangChain's RecursiveCharacterTextSplitter with size and overlap
configured from application settings.

Each output chunk dict preserves all metadata from the input item and
adds a `chunk_id` field: "{source}_{section}_{index}".
"""

import logging
import re
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import get_settings

logger = logging.getLogger(__name__)


def _safe_id(value: str) -> str:
    """Normalise a string for use inside a chunk_id (strip non-alphanumeric)."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", value)


def chunk(parsed_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Split parsed document items into overlapping text chunks.

    Args:
        parsed_items: List of dicts from any parser. Each must have at
            minimum 'text', 'source', and 'section' keys.

    Returns:
        List of chunk dicts. Each preserves the original metadata plus
        a 'chunk_id' field unique within the document.
    """
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
    )

    result: list[dict[str, Any]] = []

    for item in parsed_items:
        text: str = item.get("text", "")
        if not text.strip():
            continue

        sub_texts = splitter.split_text(text)
        source = str(item.get("source", "unknown"))
        section = str(item.get("section", "unknown"))

        for idx, sub_text in enumerate(sub_texts):
            chunk_id = f"{_safe_id(source)}_{_safe_id(section)}_{idx}"
            chunk_dict: dict[str, Any] = {
                **item,
                "text": sub_text,
                "chunk_id": chunk_id,
            }
            result.append(chunk_dict)

    logger.info("chunker: %d items → %d chunks", len(parsed_items), len(result))
    return result
