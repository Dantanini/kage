"""Tests for smart plan merge — Sonnet decides append vs overwrite."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_update(text: str, user_id: int = 12345):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = 12345
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()
    return update


class TestSmartMerge:
    """When recording a plan and one already exists, Sonnet should decide merge strategy."""

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    async def test_empty_plan_writes_directly(self):
        """No existing plan → write directly without asking Claude."""
        from bot import handle_message, plan_store, _pending_plan_record

        plan_store.consume()  # ensure empty
        _pending_plan_record[12345] = True

        update = _make_update("加 cron job")
        ctx = MagicMock()

        await handle_message(update, ctx)

        content = plan_store.read()
        assert "cron" in content

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    @patch("bot._run_claude", new_callable=AsyncMock)
    async def test_existing_plan_asks_claude_to_merge(self, mock_claude):
        """Existing plan → ask Claude to decide merge strategy."""
        from bot import handle_message, plan_store, _pending_plan_record

        plan_store.write("現有計畫：加 cron job")
        _pending_plan_record[12345] = True

        # Claude returns merged result
        mock_claude.return_value = "APPEND\n加 cron job\n加 --dry-run flag"

        update = _make_update("加 --dry-run flag")
        ctx = MagicMock()

        await handle_message(update, ctx)

        # Should have called Claude for merge decision
        assert mock_claude.called
        prompt = mock_claude.call_args[0][0]
        assert "現有計畫" in prompt or "cron" in prompt

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    @patch("bot._run_claude", new_callable=AsyncMock)
    async def test_conflict_shows_options(self, mock_claude):
        """If Claude detects conflict, should show overwrite/append buttons."""
        from bot import handle_message, plan_store, _pending_plan_record

        plan_store.write("重構 memory module")
        _pending_plan_record[12345] = True

        # Claude detects conflict
        mock_claude.return_value = "CONFLICT\n現有計畫是重構 memory，新計畫是加 cron，方向不同。"

        update = _make_update("加 cron job 到 archive")
        ctx = MagicMock()

        await handle_message(update, ctx)

        # Should show conflict buttons
        reply_call = update.message.reply_text.call_args
        assert "reply_markup" in reply_call.kwargs or "衝突" in str(reply_call)
