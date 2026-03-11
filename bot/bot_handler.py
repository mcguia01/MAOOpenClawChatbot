"""Bot Framework ActivityHandler for OpenClaw.

Handles incoming Teams messages:
  1. Extracts the user's text from the activity
  2. Maintains per-conversation chat history (in-memory)
  3. Calls rag.chain.ask() to get an answer
  4. Sends the formatted response back via the formatter

TODO: Replace the in-memory chat history dict with Azure Cosmos DB or
      Redis to support multi-instance deployments and history persistence
      across bot restarts.
"""

import logging
from typing import Any

from botbuilder.core import ActivityHandler, TurnContext
from botbuilder.schema import ActivityTypes

from bot.formatter import format_error, format_response
from rag.chain import ask

logger = logging.getLogger(__name__)

# In-memory conversation history: {conversation_id: [{"role": ..., "content": ...}]}
_conversation_history: dict[str, list[dict[str, str]]] = {}

_MAX_HISTORY_TURNS = 10  # Keep last N user+assistant turn pairs


class OpenClawBot(ActivityHandler):
    """ActivityHandler that routes Teams messages through the RAG pipeline."""

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """Handle a message sent by a user in Teams.

        Args:
            turn_context: The Bot Framework turn context for this activity.
        """
        conversation_id: str = turn_context.activity.conversation.id
        user_text: str = (turn_context.activity.text or "").strip()

        if not user_text:
            logger.debug("Received empty message in conversation '%s', ignoring", conversation_id)
            return

        logger.info("Received message in conversation '%s': %.100s", conversation_id, user_text)

        # Retrieve or initialise this conversation's history
        history = _conversation_history.setdefault(conversation_id, [])

        try:
            result = ask(query=user_text, chat_history=history)
            answer: str = result["answer"]
            sources: list[dict[str, Any]] = result["sources"]

            # Update history with this turn
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": answer})

            # Trim history to avoid unbounded growth
            if len(history) > _MAX_HISTORY_TURNS * 2:
                _conversation_history[conversation_id] = history[-(_MAX_HISTORY_TURNS * 2):]

            activity = format_response(answer=answer, sources=sources)

        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Error processing message in conversation '%s': %s",
                conversation_id,
                exc,
                exc_info=True,
            )
            activity = format_error()

        await turn_context.send_activity(activity)

    async def on_members_added_activity(
        self, members_added: list[Any], turn_context: TurnContext
    ) -> None:
        """Send a welcome message when the bot is added to a conversation."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "Hi! I'm **OpenClaw**, your MAO process document assistant. "
                    "Ask me anything about Manhattan Active Omni processes and SOPs."
                )
