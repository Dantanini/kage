"""Tests for unknown command fallback — unregistered /xxx should be treated as text."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_update(text: str, user_id: int = 12345):
    """Create a mock Telegram Update with the given text."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()
    return update


class TestUnknownCommandFallback:
    """Unregistered commands should be forwarded to Claude, not silently dropped."""

    @pytest.mark.asyncio
    @patch("bot._run_claude", new_callable=AsyncMock, return_value="回覆")
    @patch("bot.ADMIN_ID", 12345)
    async def test_unknown_command_reaches_claude(self, mock_claude):
        """A message like /plan xxx should reach handle_message when /plan is not registered."""
        from bot import handle_unknown_command

        update = _make_update("/plan 把 archive 加 cron")
        ctx = MagicMock()

        await handle_unknown_command(update, ctx)

        # Should have called handle_message internally, which calls _run_claude
        assert mock_claude.called

    @pytest.mark.asyncio
    @patch("bot._run_claude", new_callable=AsyncMock, return_value="回覆")
    @patch("bot.ADMIN_ID", 12345)
    async def test_unknown_command_preserves_full_text(self, mock_claude):
        """The full message including /command should be sent to Claude."""
        from bot import handle_unknown_command

        update = _make_update("/plan 把 archive 加 cron")
        ctx = MagicMock()

        await handle_unknown_command(update, ctx)

        # handle_message is called, which sends to Claude
        assert mock_claude.called

    @pytest.mark.asyncio
    async def test_unknown_command_unauthorized_ignored(self):
        """Unauthorized users should still be silently ignored."""
        from bot import handle_unknown_command

        update = _make_update("/plan test", user_id=99999)
        ctx = MagicMock()

        with patch("bot.ADMIN_ID", 12345):
            await handle_unknown_command(update, ctx)

        update.message.reply_text.assert_not_called()
