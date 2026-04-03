"""Tests for /plan bot command integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot import cmd_plan, handle_callback, handle_message, plan_store, sessions


def _make_update(text: str, user_id: int = 123):
    """Create a mock Telegram Update with message."""
    update = AsyncMock()
    update.effective_user = MagicMock(id=user_id)
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.reply_to_message = None
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
    async def test_plan_no_args_shows_buttons_no_plan(self):
        """With no plan, /plan shows 📭 status and button menu."""
        update = _make_update("/plan")
        ctx = AsyncMock()
        await cmd_plan(update, ctx)
        call_kwargs = update.message.reply_text.call_args
        reply_text = call_kwargs[0][0]
        assert "📭" in reply_text
        assert "選擇操作" in reply_text
        assert call_kwargs[1].get("reply_markup") is not None

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_plan_no_args_shows_buttons_with_plan(self):
        """With existing plan, /plan shows 📋 status and button menu."""
        plan_store.write("Do important thing")
        update = _make_update("/plan")
        ctx = AsyncMock()
        await cmd_plan(update, ctx)
        call_kwargs = update.message.reply_text.call_args
        reply_text = call_kwargs[0][0]
        assert "📋" in reply_text
        assert "選擇操作" in reply_text

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_plan_write(self):
        update = _make_update("/plan 1. Define State\n2. Write tests")
        ctx = AsyncMock()
        await cmd_plan(update, ctx)
        reply = update.message.reply_text.call_args[0][0]
        assert "已記錄" in reply
        assert plan_store.has_plan()

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_plan_write_has_start_button(self):
        """Recording a plan via /plan <text> should include ▶️ 開始計畫 button."""
        update = _make_update("/plan Do important thing")
        ctx = AsyncMock()
        await cmd_plan(update, ctx)
        call_kwargs = update.message.reply_text.call_args[1]
        markup = call_kwargs.get("reply_markup")
        assert markup is not None
        buttons = [btn.callback_data for row in markup.inline_keyboard for btn in row]
        assert "plan_start" in buttons


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


def _make_callback_query(action: str, user_id: int = 123, chat_id: int = 456):
    """Create a mock callback query for button press tests."""
    query = AsyncMock()
    query.data = action
    query.from_user = MagicMock(id=user_id)
    query.message = MagicMock()
    query.message.chat_id = chat_id
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    return query


class TestPlanStartSessionModel:
    """plan_start sets session to opus; plan_confirm_impl resets to sonnet."""

    @pytest.fixture(autouse=True)
    def clean(self):
        plan_store.consume()
        sessions.close_sync(123)
        yield
        plan_store.consume()
        sessions.close_sync(123)

    @patch("bot.ADMIN_ID", 123)
    @patch("bot._run_claude", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_plan_start_sets_opus(self, mock_claude):
        """After plan_start succeeds, session.model should be 'opus'."""
        plan_store.write("Build feature X")
        mock_claude.return_value = "- [ ] Step 1\n- [ ] Step 2"

        query = _make_callback_query("plan_start")
        update = AsyncMock()
        update.callback_query = query
        ctx = AsyncMock()
        ctx.bot.send_message = AsyncMock()

        with patch("bot.ADMIN_ID", 123):
            await handle_callback(update, ctx)

        session = sessions.get(123)
        assert session is not None
        assert session.model == "opus"

    @patch("bot.ADMIN_ID", 123)
    @patch("bot._run_plan_impl", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_plan_confirm_impl_sets_sonnet(self, mock_impl):
        """plan_confirm_impl should set session.model to 'sonnet'."""
        # Pre-create session with opus
        sessions.create(123, "plan", "opus")

        query = _make_callback_query("plan_confirm_impl")
        update = AsyncMock()
        update.callback_query = query
        ctx = AsyncMock()

        with patch("bot.ADMIN_ID", 123):
            await handle_callback(update, ctx)

        session = sessions.get(123)
        assert session is not None
        assert session.model == "sonnet"


class TestPlanConfirmLater:
    """plan_confirm_later should preserve plan preview text, not replace it."""

    @pytest.fixture(autouse=True)
    def clean(self):
        plan_store.consume()
        yield
        plan_store.consume()

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_later_uses_edit_reply_markup_not_edit_text(self):
        """plan_confirm_later removes buttons via edit_message_reply_markup, not edit_message_text."""
        plan_store.write("My plan")

        query = _make_callback_query("plan_confirm_later")
        update = AsyncMock()
        update.callback_query = query
        ctx = AsyncMock()
        ctx.bot.send_message = AsyncMock()

        with patch("bot.ADMIN_ID", 123):
            await handle_callback(update, ctx)

        query.edit_message_reply_markup.assert_awaited_once()
        query.edit_message_text.assert_not_awaited()

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_later_keeps_files_intact(self):
        """plan_confirm_later should NOT consume next-session-plan.md."""
        plan_store.write("My plan")

        query = _make_callback_query("plan_confirm_later")
        update = AsyncMock()
        update.callback_query = query
        ctx = AsyncMock()
        ctx.bot.send_message = AsyncMock()

        with patch("bot.ADMIN_ID", 123):
            await handle_callback(update, ctx)

        assert plan_store.has_plan()
