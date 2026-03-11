"""Response formatter — converts RAG output to Bot Framework Activity objects.

Formats answers as Teams-compatible messages with source citations appended.
Uses plain text + markdown rather than HeroCard to maximise Teams compatibility.
"""

import logging
from typing import Any

from botbuilder.schema import Activity, ActivityTypes

logger = logging.getLogger(__name__)


def format_response(answer: str, sources: list[dict[str, Any]]) -> Activity:
    """Build a reply Activity containing the answer and source citations.

    Args:
        answer: The text answer from the RAG chain.
        sources: List of unique source dicts with 'source' and 'section' keys.

    Returns:
        A Bot Framework Activity ready to send via TurnContext.send_activity().
    """
    text_parts = [answer]

    if sources:
        citation_lines = []
        for idx, s in enumerate(sources, start=1):
            src = s.get("source", "Unknown")
            sec = s.get("section", "")
            if sec:
                citation_lines.append(f"  [{idx}] **{src}** — {sec}")
            else:
                citation_lines.append(f"  [{idx}] **{src}**")

        text_parts.append("\n\n---\n**Sources:**\n" + "\n".join(citation_lines))

    full_text = "".join(text_parts)

    activity = Activity(
        type=ActivityTypes.message,
        text=full_text,
    )
    return activity


def format_error() -> Activity:
    """Build a generic error reply Activity.

    Returns:
        A Bot Framework Activity with a user-friendly error message.
    """
    activity = Activity(
        type=ActivityTypes.message,
        text=(
            "Sorry, I ran into a problem while looking that up. "
            "Please try again in a moment, or contact your project lead if the issue persists."
        ),
    )
    return activity
