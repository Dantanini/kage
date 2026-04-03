"""Tests for /plan bot command integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot import cmd_plan, plan_store


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
