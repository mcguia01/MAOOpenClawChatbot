"""Prompt builder — assembles the messages array passed to the Anthropic API.

The system prompt instructs Claude to behave as OpenClaw and cite sources.
Context chunks are formatted as numbered source blocks. Chat history is
included for multi-turn conversation support.
"""

from typing import Any

_SYSTEM_PROMPT = """You are OpenClaw, an expert assistant for Manhattan Active Omni (MAO) consulting processes.
You answer questions exclusively based on the provided document context.
Always cite the source document and section for every claim you make.
If the answer is not found in the provided context, respond with:
"I couldn't find information about that in the MAO document repository. \
Please check with your project lead or review the source documents directly."
Never fabricate MAO-specific process details, configuration steps, or SOP instructions."""


def _format_context(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks as numbered source blocks.

    Each block looks like:
      [1] Source: filename | Section: section_name
      <chunk text>
    """
    lines: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        source = chunk.get("source", "Unknown")
        section = chunk.get("section", "Unknown")
        text = chunk.get("text", "")
        lines.append(f"[{idx}] Source: {source} | Section: {section}\n{text}")
    return "\n\n".join(lines)


def build_prompt(
    query: str,
    chunks: list[dict[str, Any]],
    chat_history: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Assemble a messages array for the Anthropic Messages API.

    Args:
        query: The current user question.
        chunks: Retrieved context chunks from the retriever.
        chat_history: List of previous turns, each a dict with
            'role' ('user' | 'assistant') and 'content' keys.

    Returns:
        A list of message dicts compatible with anthropic.Anthropic().messages.create().
        The system prompt is returned separately via the 'system' field convention —
        callers should pass `system=messages[0]["content"]` and `messages=messages[1:]`.
        This function returns the full list; the chain separates them.
    """
    context_block = _format_context(chunks)

    user_content = (
        f"Use the following document context to answer the question.\n\n"
        f"=== CONTEXT ===\n{context_block}\n\n"
        f"=== QUESTION ===\n{query}"
    )

    messages: list[dict[str, str]] = []

    # Inject prior chat history
    for turn in chat_history:
        messages.append({"role": turn["role"], "content": turn["content"]})

    # Current user turn
    messages.append({"role": "user", "content": user_content})

    return messages


def get_system_prompt() -> str:
    """Return the static system prompt for OpenClaw."""
    return _SYSTEM_PROMPT
