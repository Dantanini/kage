"""Tests for task_pr and task_ask callback handling in bot.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot import handle_callback, handle_message, _pending_task_ask


def _make_callback_query(action: str, user_id: int = 123, chat_id: int = 456):
    """Create a mock callback query update."""
    update = AsyncMock()
    update.callback_query.data = action
    update.callback_query.from_user = MagicMock(id=user_id)
    update.callback_query.message.chat_id = chat_id
    update.effective_chat = MagicMock(id=chat_id)
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


def _make_message(text: str, user_id: int = 123, chat_id: int = 456):
    """Create a mock text message update."""
    update = AsyncMock()
    update.effective_user = MagicMock(id=user_id)
    update.effective_chat = MagicMock(id=chat_id)
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()
    return update


class TestTaskPrCallback:
    """task_pr:<branch> should run scripts/pr.sh for that branch."""

    @pytest.fixture(autouse=True)
    def clean_state(self):
        _pending_task_ask.clear()
        yield
        _pending_task_ask.clear()

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_task_pr_runs_pr_script(self, mock_exec):
        """Should call scripts/pr.sh with the branch name."""
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"https://github.com/x/y/pull/1", b""))
        proc.returncode = 0
        mock_exec.return_value = proc

        update = _make_callback_query("task_pr:feat/test-branch")
        ctx = AsyncMock()
        await handle_callback(update, ctx)

        mock_exec.assert_called_once()
        call_args = mock_exec.call_args[0]
        assert "pr.sh" in str(call_args)
        assert "feat/test-branch" in call_args

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_task_pr_shows_result(self, mock_exec):
        """Should show PR URL on success."""
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"https://github.com/x/y/pull/42", b""))
        proc.returncode = 0
        mock_exec.return_value = proc

        update = _make_callback_query("task_pr:feat/x")
        ctx = AsyncMock()
        await handle_callback(update, ctx)

        send_text = ctx.bot.send_message.call_args[0][1]
        assert "pull/42" in send_text

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_task_pr_shows_error(self, mock_exec):
        """Should show error when pr.sh fails."""
        proc = AsyncMock()
        proc.communicate = AsyncMock(return_value=(b"", "禁止從 main 開 PR".encode()))
        proc.returncode = 1
        mock_exec.return_value = proc

        update = _make_callback_query("task_pr:main")
        ctx = AsyncMock()
        await handle_callback(update, ctx)

        send_text = ctx.bot.send_message.call_args[0][1]
        assert "失敗" in send_text


class TestTaskAskCallback:
    """task_ask:<branch> should enter Q&A mode for that branch."""

    @pytest.fixture(autouse=True)
    def clean_state(self):
        _pending_task_ask.clear()
        yield
        _pending_task_ask.clear()

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_sets_pending_state(self):
        """Should store branch in _pending_task_ask."""
        update = _make_callback_query("task_ask:feat/guard", chat_id=789)
        ctx = AsyncMock()
        await handle_callback(update, ctx)

        assert 789 in _pending_task_ask
        assert _pending_task_ask[789] == "feat/guard"

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_prompts_user(self):
        """Should ask user to type their question."""
        update = _make_callback_query("task_ask:feat/x")
        ctx = AsyncMock()
        await handle_callback(update, ctx)

        edit_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "feat/x" in edit_text

    @patch("bot.ADMIN_ID", 123)
    @patch("bot._run_claude", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_question_goes_to_claude_with_branch_context(self, mock_claude):
        """When user types after task_ask, Claude should know the branch."""
        mock_claude.return_value = "這個 branch 加了 guard"

        # Set pending state
        _pending_task_ask[456] = "feat/branch-guard"

        update = _make_message("這個 branch 的測試覆蓋了什麼？", chat_id=456)
        ctx = AsyncMock()
        await handle_message(update, ctx)

        # Claude should receive prompt with branch context
        prompt_sent = mock_claude.call_args[0][0]
        assert "feat/branch-guard" in prompt_sent

    @patch("bot.ADMIN_ID", 123)
    @patch("bot._run_claude", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_answer_shows_buttons_again(self, mock_claude):
        """After answering, should show [開 PR] [追問] buttons again."""
        mock_claude.return_value = "答案"

        _pending_task_ask[456] = "feat/x"

        update = _make_message("問題？", chat_id=456)
        ctx = AsyncMock()
        await handle_message(update, ctx)

        # Should have reply_text called with reply_markup (buttons)
        calls = update.message.reply_text.call_args_list
        # Find the call that has reply_markup
        has_buttons = any(
            c[1].get("reply_markup") is not None
            for c in calls
            if c[1]  # has kwargs
        )
        assert has_buttons, "Answer should include inline buttons"

    @patch("bot.ADMIN_ID", 123)
    @patch("bot._run_claude", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_clears_pending_after_answer(self, mock_claude):
        """Should clear pending state after answering (buttons will re-set it if needed)."""
        mock_claude.return_value = "答案"
        _pending_task_ask[456] = "feat/x"

        update = _make_message("問題？", chat_id=456)
        ctx = AsyncMock()
        await handle_message(update, ctx)

        assert 456 not in _pending_task_ask
