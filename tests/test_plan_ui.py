"""Tests for /plan inline button UI and related callbacks."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


def _make_update(text: str, user_id: int = 12345):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()
    return update


def _make_callback_query(data: str, user_id: int = 12345):
    """Create a mock callback query from inline button press."""
    query = MagicMock()
    query.from_user.id = user_id
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message.chat_id = 12345
    return query


class TestPlanButtonMenu:
    """/plan with no args should show inline keyboard buttons."""

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    async def test_plan_no_args_shows_buttons(self):
        from bot import cmd_plan

        update = _make_update("/plan")
        ctx = MagicMock()

        await cmd_plan(update, ctx)

        update.message.reply_text.assert_called_once()
        call_kwargs = update.message.reply_text.call_args
        # Should have reply_markup (inline keyboard)
        assert "reply_markup" in call_kwargs.kwargs or (
            len(call_kwargs.args) > 1 or "reply_markup" in (call_kwargs.kwargs or {})
        )

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    async def test_plan_with_text_records(self):
        """Giving text should record it directly (not show buttons)."""
        from bot import cmd_plan, plan_store

        update = _make_update("/plan 加 cron job")
        ctx = MagicMock()

        await cmd_plan(update, ctx)

        content = plan_store.read()
        assert "cron" in content


class TestPlanCallbacks:
    """Test inline button callback handlers for plan operations."""

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    async def test_plan_view_callback_shows_content(self):
        from bot import handle_callback, plan_store

        plan_store.write("測試計畫內容")

        update = MagicMock()
        update.callback_query = _make_callback_query("plan_view")
        ctx = MagicMock()

        await handle_callback(update, ctx)

        query = update.callback_query
        query.edit_message_text.assert_called_once()
        text = query.edit_message_text.call_args[0][0]
        assert "測試計畫內容" in text

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    async def test_plan_view_callback_empty(self):
        from bot import handle_callback, plan_store

        # Ensure no plan
        plan_store.consume()

        update = MagicMock()
        update.callback_query = _make_callback_query("plan_view")
        ctx = MagicMock()

        await handle_callback(update, ctx)

        query = update.callback_query
        query.edit_message_text.assert_called_once()
        text = query.edit_message_text.call_args[0][0]
        assert "沒有" in text

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    async def test_plan_record_callback_prompts_input(self):
        from bot import handle_callback

        update = MagicMock()
        update.callback_query = _make_callback_query("plan_record")
        ctx = MagicMock()
        ctx.bot.send_message = AsyncMock()

        await handle_callback(update, ctx)

        query = update.callback_query
        # Should prompt user to type plan content
        assert ctx.bot.send_message.called or query.edit_message_text.called

    @pytest.mark.asyncio
    @patch("bot.ADMIN_ID", 12345)
    @patch("bot._run_claude", new_callable=AsyncMock, return_value="## 計畫\n- [ ] step 1\n- [ ] step 2")
    async def test_plan_start_callback_uses_opus(self, mock_claude):
        from bot import handle_callback, plan_store

        plan_store.write("加 cron job 到 archive script")

        update = MagicMock()
        update.callback_query = _make_callback_query("plan_start")
        ctx = MagicMock()
        ctx.bot.send_message = AsyncMock()

        await handle_callback(update, ctx)

        # Should call Claude with Opus model
        assert mock_claude.called
        call_args = mock_claude.call_args
        assert call_args[0][1] == "opus"  # model = opus
