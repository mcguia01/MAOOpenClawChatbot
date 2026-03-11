"""Unit tests for the RAG retriever.

Mocks the Pinecone vector_store.query() to test score threshold filtering
and return value shaping without requiring a real Pinecone connection.
"""

from unittest.mock import patch

import pytest

from rag.retriever import retrieve


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_chunk(score: float, text: str = "sample text") -> dict:
    return {
        "chunk_id": "doc_section_0",
        "score": score,
        "text": text,
        "source": "sample.docx",
        "section": "Introduction",
        "page": 1,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRetriever:
    @patch("rag.retriever.vector_query")
    def test_returns_chunks_above_threshold(self, mock_query) -> None:
        mock_query.return_value = [
            _make_chunk(0.9),
            _make_chunk(0.8),
        ]
        results = retrieve("What is the MAO order flow?")
        assert len(results) == 2

    @patch("rag.retriever.vector_query")
    def test_filters_chunks_below_threshold(self, mock_query) -> None:
        mock_query.return_value = [
            _make_chunk(0.9),   # above threshold (0.75)
            _make_chunk(0.5),   # below threshold
            _make_chunk(0.3),   # below threshold
        ]
        results = retrieve("MAO allocation process")
        assert len(results) == 1
        assert results[0]["score"] == 0.9

    @patch("rag.retriever.vector_query")
    def test_returns_empty_when_all_below_threshold(self, mock_query) -> None:
        mock_query.return_value = [
            _make_chunk(0.4),
            _make_chunk(0.2),
        ]
        results = retrieve("unrelated query")
        assert results == []

    @patch("rag.retriever.vector_query")
    def test_returns_empty_when_no_results(self, mock_query) -> None:
        mock_query.return_value = []
        results = retrieve("obscure query")
        assert results == []

    @patch("rag.retriever.vector_query")
    def test_passes_top_k_override(self, mock_query) -> None:
        mock_query.return_value = [_make_chunk(0.95)]
        retrieve("test query", top_k=3)
        mock_query.assert_called_once_with(query_text="test query", top_k=3)

    @patch("rag.retriever.vector_query")
    def test_result_has_expected_keys(self, mock_query) -> None:
        mock_query.return_value = [_make_chunk(0.85, text="relevant text")]
        results = retrieve("test")
        assert "text" in results[0]
        assert "source" in results[0]
        assert "section" in results[0]
        assert "score" in results[0]
