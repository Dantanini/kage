"""Tests for /deep command — switch to Opus mid-session without losing context."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from session import Session


def _make_update(text: str, user_id: int = 12345):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()
    return update


class TestDeepCommand:
    """Switch to Opus mid-session, preserving conversation context."""

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    async def test_deep_switches_model_to_opus(self):
        """After /deep, session model should be opus."""
        from bot import cmd_deep, sessions

        # Create an existing Sonnet session
        session = sessions.create(12345, "chat", "sonnet")
        session.qa_log.append(("你好", "你好！"))
        session.is_first_message = False

        update = _make_update("/deep")
        ctx = MagicMock()

        await cmd_deep(update, ctx)

        assert session.model == "opus"
        # Confirm message sent
        update.message.reply_text.assert_called_once()
        reply_text = update.message.reply_text.call_args[0][0]
        assert "opus" in reply_text.lower() or "Opus" in reply_text

        # Cleanup
        sessions.close_sync(12345)

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    async def test_deep_preserves_qa_log(self):
        """QA log should be preserved after switching to Opus."""
        from bot import cmd_deep, sessions

        session = sessions.create(12345, "chat", "sonnet")
        session.qa_log.append(("問題1", "回答1"))
        session.qa_log.append(("問題2", "回答2"))
        session.is_first_message = False

        update = _make_update("/deep")
        ctx = MagicMock()

        await cmd_deep(update, ctx)

        assert len(session.qa_log) == 2
        assert session.qa_log[0] == ("問題1", "回答1")

        sessions.close_sync(12345)

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    async def test_deep_preserves_session_id(self):
        """Session ID should stay the same — this is the same session."""
        from bot import cmd_deep, sessions

        session = sessions.create(12345, "chat", "sonnet")
        original_id = session.session_id
        session.is_first_message = False

        update = _make_update("/deep")
        ctx = MagicMock()

        await cmd_deep(update, ctx)

        assert session.session_id == original_id

        sessions.close_sync(12345)

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    async def test_deep_no_session_creates_opus_session(self):
        """If no session exists, /deep should create a new Opus session."""
        from bot import cmd_deep, sessions

        # Ensure no session
        sessions.close_sync(12345)

        update = _make_update("/deep")
        ctx = MagicMock()

        await cmd_deep(update, ctx)

        session = sessions.get(12345)
        assert session is not None
        assert session.model == "opus"

        sessions.close_sync(12345)

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    async def test_deep_with_text_switches_and_sends(self):
        """/deep 幫我分析 should switch to Opus AND send the text to Claude."""
        from bot import cmd_deep, sessions

        session = sessions.create(12345, "chat", "sonnet")
        session.is_first_message = False

        update = _make_update("/deep 幫我分析這個架構")
        ctx = MagicMock()

        with patch("bot._run_claude", new_callable=AsyncMock, return_value="分析結果") as mock_claude:
            await cmd_deep(update, ctx)

        assert session.model == "opus"
        # Should have called Claude with the text
        assert mock_claude.called
        call_args = mock_claude.call_args
        assert "幫我分析這個架構" in call_args[0][0]
        assert call_args[0][1] == "opus"  # model should be opus

        sessions.close_sync(12345)
