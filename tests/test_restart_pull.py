"""Tests for /restart git pull behavior."""

from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


def _make_update(text: str = "/restart", user_id: int = 123):
    update = AsyncMock()
    update.effective_user = MagicMock(id=user_id)
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


class TestRestartPull:
    """Restart should pull both repos before exiting."""

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_restart_pulls_both_repos(self, mock_pull, mock_sleep, mock_exit):
        """Restart should git pull both kage and journal repos."""
        from bot import cmd_restart, REPOS, REPO_DIR
        mock_pull.return_value = None  # success

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
    @pytest.mark.asyncio
    async def test_restart_notifies_pull_failure(self, mock_pull, mock_sleep, mock_exit):
        """If git pull fails, user should see a warning."""
        from bot import cmd_restart
        mock_pull.return_value = "git pull 失敗: merge conflict"

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
    @pytest.mark.asyncio
    async def test_restart_continues_even_if_pull_fails(self, mock_pull, mock_sleep, mock_exit):
        """Pull failure should NOT block restart."""
        from bot import cmd_restart
        mock_pull.return_value = "git pull 失敗: conflict"

        update = _make_update()
        ctx = AsyncMock()
        await cmd_restart(update, ctx)

        # Should still exit (restart)
        mock_exit.assert_called_once_with(0)

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_restart_saves_memory_before_pull(self, mock_pull, mock_sleep, mock_exit):
        """Memory should be saved before pull (existing behavior preserved)."""
        from bot import cmd_restart, sessions
        mock_pull.return_value = None

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
