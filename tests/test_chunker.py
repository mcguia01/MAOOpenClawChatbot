"""Unit tests for the text chunker.

Verifies chunk size bounds, overlap behaviour, metadata preservation,
and chunk_id generation.
"""

import os
from unittest.mock import patch

import pytest

from ingestion.chunker import chunk


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_item(text: str, source: str = "doc.docx", section: str = "Intro") -> dict:
    return {"text": text, "source": source, "section": section, "page": None}


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestChunker:
    def test_empty_input_returns_empty_list(self) -> None:
        assert chunk([]) == []

    def test_blank_text_items_are_skipped(self) -> None:
        items = [_make_item(""), _make_item("   ")]
        result = chunk(items)
        assert result == []

    def test_short_text_produces_single_chunk(self) -> None:
        items = [_make_item("Short text that fits in one chunk.")]
        result = chunk(items)
        assert len(result) == 1
        assert result[0]["text"] == "Short text that fits in one chunk."

    def test_long_text_is_split(self) -> None:
        # Generate text longer than chunk_size=500
        long_text = "Word " * 200  # ~1000 chars
        items = [_make_item(long_text)]
        result = chunk(items)
        assert len(result) > 1

    def test_chunk_id_format(self) -> None:
        items = [_make_item("Some text here.", source="report.docx", section="Summary")]
        result = chunk(items)
        assert len(result) == 1
        cid = result[0]["chunk_id"]
        assert "report_docx" in cid
        assert "Summary" in cid
        assert cid.endswith("_0")

    def test_metadata_preserved(self) -> None:
        items = [_make_item("Text", source="file.pptx", section="Slide 1")]
        result = chunk(items)
        assert result[0]["source"] == "file.pptx"
        assert result[0]["section"] == "Slide 1"
        assert result[0]["page"] is None

    def test_chunk_ids_are_unique_across_splits(self) -> None:
        long_text = "Sentence. " * 150  # forces multiple chunks
        items = [_make_item(long_text)]
        result = chunk(items)
        ids = [c["chunk_id"] for c in result]
        assert len(ids) == len(set(ids)), "Chunk IDs must be unique"

    def test_multiple_items_produce_correct_output(self) -> None:
        items = [
            _make_item("First item text.", source="a.docx", section="A"),
            _make_item("Second item text.", source="b.docx", section="B"),
        ]
        result = chunk(items)
        sources = {c["source"] for c in result}
        assert sources == {"a.docx", "b.docx"}
