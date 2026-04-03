"""Tests for /plan bot command integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot import cmd_plan, handle_message, plan_store


def _make_update(text: str, user_id: int = 123):
    """Create a mock Telegram Update with message."""
    update = AsyncMock()
    update.effective_user = MagicMock(id=user_id)
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


class TestPlanCommand:
    """Test /plan Telegram command."""

    @pytest.fixture(autouse=True)
    def clean_plan(self):
        """Ensure no leftover plan between tests."""
        plan_store.consume()
        yield
        plan_store.consume()

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_plan_no_args_shows_empty(self):
        update = _make_update("/plan")
        ctx = AsyncMock()
        await cmd_plan(update, ctx)
        reply = update.message.reply_text.call_args[0][0]
        assert "沒有待執行的計畫" in reply

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_plan_write(self):
        update = _make_update("/plan 1. Define State\n2. Write tests")
        ctx = AsyncMock()
        await cmd_plan(update, ctx)
        reply = update.message.reply_text.call_args[0][0]
        assert "已儲存" in reply
        assert plan_store.has_plan()

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_plan_view_after_write(self):
        plan_store.write("Do important thing")
        update = _make_update("/plan")
        ctx = AsyncMock()
        await cmd_plan(update, ctx)
        reply = update.message.reply_text.call_args[0][0]
        assert "Do important thing" in reply

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_plan_append(self):
        plan_store.write("Step 1")
        update = _make_update("/plan + Step 2")
        ctx = AsyncMock()
        await cmd_plan(update, ctx)
        reply = update.message.reply_text.call_args[0][0]
        assert "追加" in reply
        assert "Step 1" in plan_store.read()
        assert "Step 2" in plan_store.read()


class TestPlanConsumeSafety:
    """Plan should only be consumed after Claude succeeds, not on injection."""

    @pytest.fixture(autouse=True)
    def clean_plan(self):
        plan_store.consume()
        yield
        plan_store.consume()

    @patch("bot.ADMIN_ID", 123)
    @patch("bot._run_claude", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_plan_survives_claude_failure(self, mock_claude):
        """If Claude returns error, plan should NOT be consumed."""
        plan_store.write("Important plan")
        mock_claude.return_value = "⚠️ Claude 執行失敗"

        update = _make_update("開始工作")
        update.message.chat.send_action = AsyncMock()
        ctx = AsyncMock()

        await handle_message(update, ctx)

        # Plan should still exist because Claude failed
        assert plan_store.has_plan()
        assert "Important plan" in plan_store.read()

    @patch("bot.ADMIN_ID", 123)
    @patch("bot._run_claude", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_plan_consumed_after_claude_success(self, mock_claude):
        """If Claude succeeds, plan should be consumed."""
        plan_store.write("Will be consumed")
        mock_claude.return_value = "好的，我來執行計畫"

        update = _make_update("開始工作")
        update.message.chat.send_action = AsyncMock()
        ctx = AsyncMock()

        await handle_message(update, ctx)

        # Plan should be consumed after success
        assert not plan_store.has_plan()
