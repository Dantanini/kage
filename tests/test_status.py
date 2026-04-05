"""Tests for /status command — monitor running claude subprocesses."""

from unittest.mock import AsyncMock, patch, MagicMock
import pytest


def _make_update(user_id=123):
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


class TestGetClaudeStatus:
    """Test _get_claude_status() process detection."""

    @pytest.mark.asyncio
    async def test_no_process_returns_none(self):
        """No claude subprocess → return None."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("bot.asyncio.create_subprocess_exec", return_value=mock_proc):
            from bot import _get_claude_status
            result = await _get_claude_status()
            assert result is None

    @pytest.mark.asyncio
    async def test_running_process_returns_info(self):
        """Detected claude process → return dict with pid, model, elapsed."""
        ps_output = b"12345 00:03:42 Sl claude -p --model opus --session-id abc"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(ps_output, b""))

        with patch("bot.asyncio.create_subprocess_exec", return_value=mock_proc):
            from bot import _get_claude_status
            result = await _get_claude_status()
            assert result is not None
            assert result["pid"] == 12345
            assert result["model"] == "opus"
            assert "3" in result["elapsed"]

    @pytest.mark.asyncio
    async def test_extracts_sonnet_model(self):
        """Should correctly extract sonnet model name."""
        ps_output = b"99999 00:01:05 Sl claude -p --model sonnet --resume xyz"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(ps_output, b""))

        with patch("bot.asyncio.create_subprocess_exec", return_value=mock_proc):
            from bot import _get_claude_status
            result = await _get_claude_status()
            assert result["model"] == "sonnet"


class TestCmdStatus:
    """Test /status command handler."""

    @pytest.mark.asyncio
    async def test_no_process_shows_idle(self):
        """/status with no running process → idle message."""
        with patch("bot._get_claude_status", return_value=None), \
             patch("bot._check_auth", return_value=True):
            from bot import cmd_status
            update = _make_update()
            await cmd_status(update, AsyncMock())
            msg = update.message.reply_text.call_args[0][0]
            assert "沒有" in msg or "閒置" in msg

    @pytest.mark.asyncio
    async def test_running_process_shows_info_with_buttons(self):
        """/status with running process → info + kill/wait buttons."""
        status = {"pid": 12345, "model": "opus", "elapsed": "03:42", "state": "Sl"}
        with patch("bot._get_claude_status", return_value=status), \
             patch("bot._check_auth", return_value=True):
            from bot import cmd_status
            update = _make_update()
            await cmd_status(update, AsyncMock())
            call_kwargs = update.message.reply_text.call_args[1]
            assert "reply_markup" in call_kwargs

    @pytest.mark.asyncio
    async def test_auth_required(self):
        """/status should check admin auth."""
        with patch("bot._check_auth", return_value=False):
            from bot import cmd_status
            update = _make_update(user_id=999)
            await cmd_status(update, AsyncMock())
            update.message.reply_text.assert_not_called()


class TestStatusKillCallback:
    """Test the kill button from /status."""

    @pytest.mark.asyncio
    async def test_kill_terminates_process(self):
        """Clicking kill button should kill the claude process."""
        with patch("bot.os.kill") as mock_kill, \
             patch("bot._get_claude_status", return_value={"pid": 12345, "model": "opus", "elapsed": "05:00", "state": "Sl"}):
            from bot import handle_callback
            query = AsyncMock()
            query.from_user = MagicMock()
            query.from_user.id = 123
            query.data = "status_kill:12345"
            query.message = AsyncMock()
            query.message.chat_id = 123
            query.answer = AsyncMock()

            update = MagicMock()
            update.callback_query = query

            ctx = AsyncMock()
            ctx.bot = AsyncMock()

            # Need to patch ADMIN_ID
            with patch("bot.ADMIN_ID", 123):
                await handle_callback(update, ctx)
                mock_kill.assert_called_once_with(12345, 15)
