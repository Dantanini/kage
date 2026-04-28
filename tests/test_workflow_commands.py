"""Tests for /morning and /evening — auth, git-pull warning, archive guard, output chunking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_update(user_id: int = 123):
    update = AsyncMock()
    update.effective_user = MagicMock(id=user_id)
    status_msg = AsyncMock()
    status_msg.delete = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=status_msg)
    return update, status_msg


def _result(success: bool):
    r = MagicMock()
    r.success = success
    return r


# ---------------------------------------------------------------------------
# /morning
# ---------------------------------------------------------------------------

class TestCmdMorning:
    @patch("bot._check_auth", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_unauthorized_user_silently_ignored(self, mock_auth):
        mock_auth.return_value = False
        from bot import cmd_morning

        update, _ = _make_update()
        await cmd_morning(update, AsyncMock())

        update.message.reply_text.assert_not_called()

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.format_workflow_results", return_value="✅ done")
    @patch("bot.run_workflow", new_callable=AsyncMock)
    @patch("bot.build_morning_steps", return_value=["step1"])
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot._get_journal_path", return_value="/tmp/journal")
    @pytest.mark.asyncio
    async def test_happy_path_runs_workflow_and_replies(
        self, mock_path, mock_pull, mock_build, mock_run, mock_fmt
    ):
        from bot import cmd_morning

        mock_pull.return_value = None
        mock_run.return_value = [_result(True)]
        update, status_msg = _make_update()

        await cmd_morning(update, AsyncMock())

        mock_run.assert_awaited_once()
        status_msg.delete.assert_awaited_once()
        replies = [c.args[0] for c in update.message.reply_text.call_args_list]
        assert "✅ done" in replies

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.format_workflow_results", return_value="ok")
    @patch("bot.run_workflow", new_callable=AsyncMock)
    @patch("bot.build_morning_steps", return_value=[])
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot._get_journal_path", return_value="/tmp/journal")
    @pytest.mark.asyncio
    async def test_git_pull_error_shown_but_continues(
        self, mock_path, mock_pull, mock_build, mock_run, mock_fmt
    ):
        from bot import cmd_morning

        mock_pull.return_value = "merge conflict"
        mock_run.return_value = [_result(True)]
        update, _ = _make_update()

        await cmd_morning(update, AsyncMock())

        replies = [c.args[0] for c in update.message.reply_text.call_args_list]
        assert any("merge conflict" in r for r in replies)
        mock_run.assert_awaited_once()

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.format_workflow_results")
    @patch("bot.run_workflow", new_callable=AsyncMock)
    @patch("bot.build_morning_steps", return_value=[])
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot._get_journal_path", return_value="/tmp/journal")
    @pytest.mark.asyncio
    async def test_long_output_is_chunked_under_4000_chars(
        self, mock_path, mock_pull, mock_build, mock_run, mock_fmt
    ):
        from bot import cmd_morning

        mock_pull.return_value = None
        mock_run.return_value = [_result(True)]
        mock_fmt.return_value = "x" * 9500
        update, _ = _make_update()

        await cmd_morning(update, AsyncMock())

        result_replies = [
            c.args[0] for c in update.message.reply_text.call_args_list
            if c.args and c.args[0].startswith("x")
        ]
        assert len(result_replies) == 3
        assert all(len(r) <= 4000 for r in result_replies)


# ---------------------------------------------------------------------------
# /evening
# ---------------------------------------------------------------------------

class TestCmdEvening:
    @patch("bot._check_auth", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_unauthorized_user_silently_ignored(self, mock_auth):
        mock_auth.return_value = False
        from bot import cmd_evening

        update, _ = _make_update()
        await cmd_evening(update, AsyncMock())

        update.message.reply_text.assert_not_called()

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.plan_store")
    @patch("bot.format_workflow_results", return_value="ok")
    @patch("bot.run_workflow", new_callable=AsyncMock)
    @patch("bot.build_evening_steps", return_value=["s"])
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot._get_journal_path", return_value="/tmp/journal")
    @pytest.mark.asyncio
    async def test_archives_when_completed_items_and_workflow_succeeds(
        self, mock_path, mock_pull, mock_build, mock_run, mock_fmt, mock_plan
    ):
        from bot import cmd_evening

        mock_pull.return_value = None
        mock_plan.read_completed.return_value = ["task A done"]
        mock_run.return_value = [_result(True), _result(True)]
        update, _ = _make_update()

        await cmd_evening(update, AsyncMock())

        mock_plan.archive_completed.assert_called_once()

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.plan_store")
    @patch("bot.format_workflow_results", return_value="ok")
    @patch("bot.run_workflow", new_callable=AsyncMock)
    @patch("bot.build_evening_steps", return_value=["s"])
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot._get_journal_path", return_value="/tmp/journal")
    @pytest.mark.asyncio
    async def test_does_not_archive_when_no_completed_items(
        self, mock_path, mock_pull, mock_build, mock_run, mock_fmt, mock_plan
    ):
        from bot import cmd_evening

        mock_pull.return_value = None
        mock_plan.read_completed.return_value = []
        mock_run.return_value = [_result(True)]
        update, _ = _make_update()

        await cmd_evening(update, AsyncMock())

        mock_plan.archive_completed.assert_not_called()

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.plan_store")
    @patch("bot.format_workflow_results", return_value="ok")
    @patch("bot.run_workflow", new_callable=AsyncMock)
    @patch("bot.build_evening_steps", return_value=["s"])
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot._get_journal_path", return_value="/tmp/journal")
    @pytest.mark.asyncio
    async def test_does_not_archive_when_last_step_failed(
        self, mock_path, mock_pull, mock_build, mock_run, mock_fmt, mock_plan
    ):
        from bot import cmd_evening

        mock_pull.return_value = None
        mock_plan.read_completed.return_value = ["task A done"]
        mock_run.return_value = [_result(True), _result(False)]
        update, _ = _make_update()

        await cmd_evening(update, AsyncMock())

        mock_plan.archive_completed.assert_not_called()
