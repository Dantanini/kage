"""Tests for /restart git pull behavior."""

from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


def _make_update(text: str = "/restart", user_id: int = 123, chat_id: int = 456):
    update = AsyncMock()
    update.effective_user = MagicMock(id=user_id)
    update.effective_chat = MagicMock(id=chat_id)
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


class TestRestartPull:
    """Restart should pull both repos before exiting."""

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_restart_pulls_both_repos(
        self, mock_subprocess, mock_pull, mock_sleep, mock_exit
    ):
        """Restart should git pull both kage and journal repos."""
        from bot import cmd_restart, REPOS, REPO_DIR
        mock_pull.return_value = None  # success
        mock_subprocess.return_value = AsyncMock(communicate=AsyncMock(return_value=(b"", b"")))

        update = _make_update()
        ctx = AsyncMock()
        await cmd_restart(update, ctx)

        # Should pull both repos
        pull_paths = [c.args[0] for c in mock_pull.call_args_list]
        assert str(REPO_DIR) in pull_paths, "Should pull kage repo"
        assert REPOS["journal"] in pull_paths, "Should pull journal repo"

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_restart_notifies_pull_failure(
        self, mock_subprocess, mock_pull, mock_sleep, mock_exit
    ):
        """If git pull fails, user should see a warning."""
        from bot import cmd_restart
        mock_pull.return_value = "git pull 失敗: merge conflict"
        mock_subprocess.return_value = AsyncMock(communicate=AsyncMock(return_value=(b"", b"")))

        update = _make_update()
        ctx = AsyncMock()
        await cmd_restart(update, ctx)

        # Should show warning about pull failure
        replies = [c.args[0] for c in update.message.reply_text.call_args_list]
        assert any("pull" in r.lower() or "失敗" in r for r in replies)

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_restart_continues_even_if_pull_fails(
        self, mock_subprocess, mock_pull, mock_sleep, mock_exit
    ):
        """Pull failure should NOT block restart."""
        from bot import cmd_restart
        mock_pull.return_value = "git pull 失敗: conflict"
        mock_subprocess.return_value = AsyncMock(communicate=AsyncMock(return_value=(b"", b"")))

        update = _make_update()
        ctx = AsyncMock()
        await cmd_restart(update, ctx)

        # Should still exit (restart)
        mock_exit.assert_called_once_with(0)

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_restart_saves_memory_before_pull(
        self, mock_subprocess, mock_pull, mock_sleep, mock_exit
    ):
        """Memory should be saved before pull (existing behavior preserved)."""
        from bot import cmd_restart, sessions
        mock_pull.return_value = None
        mock_subprocess.return_value = AsyncMock(communicate=AsyncMock(return_value=(b"", b"")))

        # Create a session with qa_log
        session = sessions.get_or_create(123, "chat", "sonnet")
        session.qa_log.append(("test q", "test a"))

        update = _make_update()
        ctx = AsyncMock()

        with patch.object(sessions, "close", new_callable=AsyncMock) as mock_close:
            await cmd_restart(update, ctx)
            mock_close.assert_called_once_with(123)

        # Clean up
        sessions._sessions.pop(123, None)


class TestRestartNotify:
    """Restart should write notify file; post_init should send notification."""

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_restart_writes_notify_file(self, mock_pull, mock_sleep, mock_exit, tmp_path):
        """cmd_restart should write .restart_notify with chat_id before exit."""
        import bot
        mock_pull.return_value = None
        original_repo_dir = bot.REPO_DIR

        with patch.object(bot, "REPO_DIR", tmp_path):
            update = _make_update(chat_id=456)
            ctx = AsyncMock()
            await bot.cmd_restart(update, ctx)

        notify_file = tmp_path / ".restart_notify"
        assert notify_file.exists(), ".restart_notify should be written before exit"
        assert notify_file.read_text().strip() == "456"

    @pytest.mark.asyncio
    async def test_post_init_sends_notify_and_deletes_file(self, tmp_path):
        """post_init should send restart notification and delete .restart_notify."""
        import bot

        notify_file = tmp_path / ".restart_notify"
        notify_file.write_text("456")

        mock_app = MagicMock()
        mock_app.bot.set_my_commands = AsyncMock()
        mock_app.bot.send_message = AsyncMock()

        with patch.object(bot, "REPO_DIR", tmp_path):
            await bot.post_init(mock_app)

        mock_app.bot.send_message.assert_called_once()
        call_kwargs = mock_app.bot.send_message.call_args
        assert call_kwargs[0][0] == 456 or call_kwargs[1].get("chat_id") == 456
        assert not notify_file.exists(), ".restart_notify should be deleted after notification"

    @pytest.mark.asyncio
    async def test_post_init_no_notify_file(self, tmp_path):
        """post_init should not send notification if .restart_notify doesn't exist."""
        import bot

        mock_app = MagicMock()
        mock_app.bot.set_my_commands = AsyncMock()
        mock_app.bot.send_message = AsyncMock()

        with patch.object(bot, "REPO_DIR", tmp_path):
            await bot.post_init(mock_app)

        mock_app.bot.send_message.assert_not_called()
