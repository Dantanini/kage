"""Tests: restart always proceeds even on git errors, but reports them first.

Core invariant: os._exit(0) is ALWAYS called, regardless of git errors.
Error messages must reach the user BEFORE restart.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_update(user_id: int = 123, chat_id: int = 456):
    update = AsyncMock()
    update.effective_user = MagicMock(id=user_id)
    update.effective_chat = MagicMock(id=chat_id)
    update.message.text = "/restart"
    update.message.reply_text = AsyncMock()
    return update


def _make_subprocess_mock(returncode=0, stdout=b"", stderr=b""):
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


def _get_all_replies(update):
    return [c.args[0] for c in update.message.reply_text.call_args_list]


class TestRestartAlwaysProceeds:
    """os._exit(0) must be called regardless of git errors."""

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_checkout_fails_restart_proceeds(
        self, mock_subprocess, mock_pull, mock_sleep, mock_exit
    ):
        """git checkout failure must NOT block restart."""
        from bot import cmd_restart

        mock_subprocess.return_value = _make_subprocess_mock(
            returncode=1, stderr=b"error: Your local changes would be overwritten"
        )
        mock_pull.return_value = None

        update = _make_update()
        await cmd_restart(update, AsyncMock())

        mock_exit.assert_called_once_with(0)

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_pull_fails_restart_proceeds(
        self, mock_subprocess, mock_pull, mock_sleep, mock_exit
    ):
        """git pull failure must NOT block restart."""
        from bot import cmd_restart

        mock_subprocess.return_value = _make_subprocess_mock(returncode=0)
        mock_pull.return_value = "CONFLICT (content): Merge conflict in bot.py"

        update = _make_update()
        await cmd_restart(update, AsyncMock())

        mock_exit.assert_called_once_with(0)

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_all_git_ops_fail_restart_still_proceeds(
        self, mock_subprocess, mock_pull, mock_sleep, mock_exit
    ):
        """Even if ALL git operations fail, restart must proceed."""
        from bot import cmd_restart

        mock_subprocess.return_value = _make_subprocess_mock(
            returncode=128, stderr=b"fatal: not a git repository"
        )
        mock_pull.return_value = "Connection refused"

        update = _make_update()
        await cmd_restart(update, AsyncMock())

        mock_exit.assert_called_once_with(0)


class TestRestartReportsErrors:
    """Error details must be sent to user BEFORE restart."""

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_checkout_error_reported(
        self, mock_subprocess, mock_pull, mock_sleep, mock_exit
    ):
        """Checkout error details must appear in user message."""
        from bot import cmd_restart

        mock_subprocess.return_value = _make_subprocess_mock(
            returncode=1, stderr=b"error: Your local changes would be overwritten"
        )
        mock_pull.return_value = None

        update = _make_update()
        await cmd_restart(update, AsyncMock())

        replies = _get_all_replies(update)
        error_replies = [r for r in replies if "overwritten" in r]
        assert error_replies, f"Checkout error not reported. Replies: {replies}"

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_pull_error_reported(
        self, mock_subprocess, mock_pull, mock_sleep, mock_exit
    ):
        """Pull error details must appear in user message."""
        from bot import cmd_restart

        mock_subprocess.return_value = _make_subprocess_mock(returncode=0)
        mock_pull.return_value = "CONFLICT (content): Merge conflict in bot.py"

        update = _make_update()
        await cmd_restart(update, AsyncMock())

        replies = _get_all_replies(update)
        error_replies = [r for r in replies if "CONFLICT" in r]
        assert error_replies, f"Pull error not reported. Replies: {replies}"

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_multiple_errors_all_reported(
        self, mock_subprocess, mock_pull, mock_sleep, mock_exit
    ):
        """All errors (checkout + pull) must be reported, not just the first."""
        from bot import cmd_restart

        mock_subprocess.return_value = _make_subprocess_mock(
            returncode=1, stderr=b"checkout failed"
        )
        mock_pull.return_value = "pull failed"

        update = _make_update()
        await cmd_restart(update, AsyncMock())

        replies = _get_all_replies(update)
        all_text = "\n".join(replies)
        assert "checkout" in all_text.lower(), f"Checkout error missing. All: {all_text}"
        assert "pull failed" in all_text, f"Pull error missing. All: {all_text}"

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_no_error_no_warning(
        self, mock_subprocess, mock_pull, mock_sleep, mock_exit
    ):
        """When git succeeds, no error/warning message should appear."""
        from bot import cmd_restart

        mock_subprocess.return_value = _make_subprocess_mock(returncode=0)
        mock_pull.return_value = None

        update = _make_update()
        await cmd_restart(update, AsyncMock())

        replies = _get_all_replies(update)
        warning_replies = [r for r in replies if "⚠️" in r or "失敗" in r]
        assert not warning_replies, f"Unexpected warning: {warning_replies}"

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.os._exit")
    @patch("bot.asyncio.sleep", new_callable=AsyncMock)
    @patch("bot._git_pull", new_callable=AsyncMock)
    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_error_sent_before_restart(
        self, mock_subprocess, mock_pull, mock_sleep, mock_exit
    ):
        """Error message must be sent BEFORE os._exit (i.e., before restart)."""
        from bot import cmd_restart

        mock_subprocess.return_value = _make_subprocess_mock(
            returncode=1, stderr=b"checkout error"
        )
        mock_pull.return_value = None

        call_order = []
        original_reply = AsyncMock()

        async def track_reply(text, *args, **kwargs):
            call_order.append(("reply", text))

        update = _make_update()
        update.message.reply_text = AsyncMock(side_effect=track_reply)

        def track_exit(code):
            call_order.append(("exit", code))

        mock_exit.side_effect = track_exit

        await cmd_restart(update, AsyncMock())

        # Find error message and exit in call order
        error_idx = next(
            (i for i, (t, v) in enumerate(call_order) if t == "reply" and "checkout" in str(v).lower()),
            None,
        )
        exit_idx = next(
            (i for i, (t, v) in enumerate(call_order) if t == "exit"),
            None,
        )
        assert error_idx is not None, f"Error message not found. Order: {call_order}"
        assert exit_idx is not None, f"os._exit not called. Order: {call_order}"
        assert error_idx < exit_idx, f"Error sent AFTER exit! Order: {call_order}"
