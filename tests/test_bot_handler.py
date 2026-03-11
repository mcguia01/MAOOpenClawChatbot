"""Unit tests for the Teams bot handler.

Mocks rag.chain.ask() to test message routing, reply formatting,
and per-conversation history tracking — no real API calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.bot_handler import OpenClawBot, _conversation_history


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_turn_context(text: str, conversation_id: str = "conv-001") -> MagicMock:
    """Return a minimal mock TurnContext with the given message text."""
    activity = MagicMock()
    activity.text = text
    activity.conversation.id = conversation_id
    activity.recipient.id = "bot-id"

    ctx = MagicMock()
    ctx.activity = activity
    ctx.send_activity = AsyncMock()
    return ctx


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestOpenClawBot:
    def setup_method(self) -> None:
        # Clear global history before each test
        _conversation_history.clear()

    @pytest.mark.asyncio
    @patch("bot.bot_handler.ask")
    async def test_sends_reply_on_valid_message(self, mock_ask) -> None:
        mock_ask.return_value = {
            "answer": "The MAO order flow starts with capture.",
            "sources": [{"source": "sop.docx", "section": "Order Flow"}],
        }
        bot = OpenClawBot()
        ctx = _make_turn_context("What is the order flow?")

        await bot.on_message_activity(ctx)

        ctx.send_activity.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("bot.bot_handler.ask")
    async def test_history_updated_after_turn(self, mock_ask) -> None:
        mock_ask.return_value = {"answer": "Answer text.", "sources": []}
        bot = OpenClawBot()
        ctx = _make_turn_context("Hello?", conversation_id="conv-history-test")

        await bot.on_message_activity(ctx)

        history = _conversation_history.get("conv-history-test", [])
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "Hello?"}
        assert history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    @patch("bot.bot_handler.ask")
    async def test_history_passed_to_ask_on_second_turn(self, mock_ask) -> None:
        mock_ask.return_value = {"answer": "First answer.", "sources": []}
        bot = OpenClawBot()
        ctx = _make_turn_context("First message", conversation_id="conv-multi")

        await bot.on_message_activity(ctx)

        mock_ask.return_value = {"answer": "Second answer.", "sources": []}
        ctx2 = _make_turn_context("Second message", conversation_id="conv-multi")
        await bot.on_message_activity(ctx2)

        # Second call should include the first turn in history
        call_kwargs = mock_ask.call_args_list[1][1]
        assert len(call_kwargs["chat_history"]) == 2

    @pytest.mark.asyncio
    async def test_empty_message_is_ignored(self) -> None:
        bot = OpenClawBot()
        ctx = _make_turn_context("")

        await bot.on_message_activity(ctx)

        ctx.send_activity.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("bot.bot_handler.ask")
    async def test_error_in_ask_sends_error_reply(self, mock_ask) -> None:
        mock_ask.side_effect = RuntimeError("Pinecone unavailable")
        bot = OpenClawBot()
        ctx = _make_turn_context("Will this fail?")

        await bot.on_message_activity(ctx)

        # Should still send a reply (the error card)
        ctx.send_activity.assert_awaited_once()
        sent = ctx.send_activity.call_args[0][0]
        # Error activity text should mention "problem"
        assert "problem" in sent.text.lower()
