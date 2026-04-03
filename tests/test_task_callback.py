"""Tests for task_pr and task_ask callback handling in bot.py."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot import handle_callback, handle_message, TASK_ASK_MARKER


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


def _make_message(text: str, user_id: int = 123, chat_id: int = 456,
                  reply_to_text: str | None = None):
    """Create a mock text message update, optionally replying to another message."""
    update = AsyncMock()
    update.effective_user = MagicMock(id=user_id)
    update.effective_chat = MagicMock(id=chat_id)
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()
    if reply_to_text is not None:
        update.message.reply_to_message = MagicMock()
        update.message.reply_to_message.text = reply_to_text
    else:
        update.message.reply_to_message = None
    return update


class TestTaskPrCallback:
    """task_pr:<branch> should run scripts/pr.sh for that branch."""

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
    """task_ask:<branch> should prompt user to reply with question."""

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_prompts_user_with_branch(self):
        """Should show branch name and ask user to reply."""
        update = _make_callback_query("task_ask:feat/guard")
        ctx = AsyncMock()
        await handle_callback(update, ctx)

        edit_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "feat/guard" in edit_text
        assert TASK_ASK_MARKER in edit_text

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_prompt_contains_reply_instruction(self):
        """Should tell user to reply to this message."""
        update = _make_callback_query("task_ask:feat/x")
        ctx = AsyncMock()
        await handle_callback(update, ctx)

        edit_text = update.callback_query.edit_message_text.call_args[0][0]
        assert "回覆" in edit_text


class TestTaskAskReply:
    """When user replies to a task_ask prompt, Claude should answer with branch context."""

    @patch("bot.ADMIN_ID", 123)
    @patch("bot._run_claude", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_reply_goes_to_claude_with_branch_context(self, mock_claude):
        """Reply to task_ask prompt should include branch in Claude prompt."""
        mock_claude.return_value = "這個 branch 加了 guard"

        reply_text = f"{TASK_ASK_MARKER} feat/branch-guard 提問\n\n請「回覆」這則訊息輸入你的問題："
        update = _make_message("測試覆蓋了什麼？", reply_to_text=reply_text)
        ctx = AsyncMock()
        await handle_message(update, ctx)

        prompt_sent = mock_claude.call_args[0][0]
        assert "feat/branch-guard" in prompt_sent

    @patch("bot.ADMIN_ID", 123)
    @patch("bot._run_claude", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_answer_shows_buttons_again(self, mock_claude):
        """After answering, should show [開 PR] [追問] buttons again."""
        mock_claude.return_value = "答案"

        reply_text = f"{TASK_ASK_MARKER} feat/x 提問\n\n請「回覆」這則訊息輸入你的問題："
        update = _make_message("問題？", reply_to_text=reply_text)
        ctx = AsyncMock()
        await handle_message(update, ctx)

        calls = update.message.reply_text.call_args_list
        has_buttons = any(
            c[1].get("reply_markup") is not None
            for c in calls
            if c[1]
        )
        assert has_buttons, "Answer should include inline buttons"

    @patch("bot.ADMIN_ID", 123)
    @patch("bot._run_claude", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_non_reply_message_not_intercepted(self, mock_claude):
        """Regular messages (not replying to task_ask) should not trigger Q&A."""
        mock_claude.return_value = "normal response"

        update = _make_message("隨便說的話")
        ctx = AsyncMock()
        await handle_message(update, ctx)

        # Should go through normal routing, not task_ask
        if mock_claude.called:
            prompt_sent = mock_claude.call_args[0][0]
            assert TASK_ASK_MARKER not in prompt_sent

    @patch("bot.ADMIN_ID", 123)
    @patch("bot._run_claude", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_concurrent_branches_independent(self, mock_claude):
        """Replies to different branch prompts should each get correct branch context."""
        mock_claude.return_value = "答案"

        # Reply to branch A
        reply_a = f"{TASK_ASK_MARKER} feat/branch-a 提問\n\n請「回覆」這則訊息輸入你的問題："
        update_a = _make_message("branch A 的問題", reply_to_text=reply_a)
        ctx = AsyncMock()
        await handle_message(update_a, ctx)
        prompt_a = mock_claude.call_args[0][0]
        assert "feat/branch-a" in prompt_a

        mock_claude.reset_mock()
        mock_claude.return_value = "答案 B"

        # Reply to branch B
        reply_b = f"{TASK_ASK_MARKER} feat/branch-b 提問\n\n請「回覆」這則訊息輸入你的問題："
        update_b = _make_message("branch B 的問題", reply_to_text=reply_b)
        await handle_message(update_b, ctx)
        prompt_b = mock_claude.call_args[0][0]
        assert "feat/branch-b" in prompt_b
