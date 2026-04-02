"""Tests for release inline button — preview shows button, callback executes release."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_update_with_message(user_id=123):
    """Create a mock Update with message for command handlers."""
    update = AsyncMock()
    update.effective_user = MagicMock(id=user_id)
    update.message.text = "/release"
    update.message.reply_text = AsyncMock()
    return update


def _make_callback_update(action: str, user_id=123):
    """Create a mock Update with callback_query for button clicks."""
    update = AsyncMock()
    query = AsyncMock()
    query.data = action
    query.from_user = MagicMock(id=user_id)
    query.message.chat_id = 456
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    return update


# ---------------------------------------------------------------------------
# cmd_release: preview should include inline button
# ---------------------------------------------------------------------------

class TestReleasePreviewButton:
    """cmd_release preview message should contain an inline confirm button."""

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.subprocess.run")
    @pytest.mark.asyncio
    async def test_preview_has_inline_keyboard(self, mock_run):
        """Preview message should have reply_markup with confirm button."""
        from bot import cmd_release

        mock_run.return_value = MagicMock(
            stdout="abc1234 feat: add feature\n\nTitle: Release: feat: add feature",
            stderr="",
            returncode=0,
        )

        update = _make_update_with_message()
        ctx = AsyncMock()

        await cmd_release(update, ctx)

        # Find the call that contains the preview (not the "正在檢查" status)
        calls = update.message.reply_text.call_args_list
        preview_call = [c for c in calls if "reply_markup" in c.kwargs]
        assert len(preview_call) == 1, "Preview message should have reply_markup"

        markup = preview_call[0].kwargs["reply_markup"]
        assert isinstance(markup, InlineKeyboardMarkup)

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.subprocess.run")
    @pytest.mark.asyncio
    async def test_preview_button_has_confirm_callback(self, mock_run):
        """Confirm button callback_data should be 'release_confirm'."""
        from bot import cmd_release

        mock_run.return_value = MagicMock(
            stdout="abc1234 feat: add feature\n\nTitle: Release",
            stderr="",
            returncode=0,
        )

        update = _make_update_with_message()
        ctx = AsyncMock()

        await cmd_release(update, ctx)

        calls = update.message.reply_text.call_args_list
        preview_call = [c for c in calls if "reply_markup" in c.kwargs][0]
        markup = preview_call.kwargs["reply_markup"]

        # Flatten all buttons and check callback_data
        buttons = [btn for row in markup.inline_keyboard for btn in row]
        callback_values = [btn.callback_data for btn in buttons]
        assert "release_confirm" in callback_values

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.subprocess.run")
    @pytest.mark.asyncio
    async def test_no_commits_no_button(self, mock_run):
        """When there are no commits, no inline button should be shown."""
        from bot import cmd_release

        mock_run.return_value = MagicMock(
            stdout="No commits between main and develop",
            stderr="",
            returncode=0,
        )

        update = _make_update_with_message()
        ctx = AsyncMock()

        await cmd_release(update, ctx)

        calls = update.message.reply_text.call_args_list
        preview_calls = [c for c in calls if "reply_markup" in c.kwargs]
        assert len(preview_calls) == 0, "No button when no commits"


# ---------------------------------------------------------------------------
# handle_callback: release_confirm executes release
# ---------------------------------------------------------------------------

class TestReleaseCallbackConfirm:
    """Clicking confirm button should execute release.py and report result."""

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.subprocess.run")
    @pytest.mark.asyncio
    async def test_confirm_runs_release(self, mock_run):
        """release_confirm callback should run release.py (no --dry-run)."""
        from bot import handle_callback

        mock_run.return_value = MagicMock(
            stdout="PR created: https://github.com/...",
            stderr="",
            returncode=0,
        )

        update = _make_callback_update("release_confirm")
        ctx = AsyncMock()

        await handle_callback(update, ctx)

        # Verify release.py was called without --dry-run
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "release.py" in str(args[-1])
        assert "--dry-run" not in args

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.subprocess.run")
    @pytest.mark.asyncio
    async def test_confirm_edits_message_with_result(self, mock_run):
        """After release, the original message should be edited with the result."""
        from bot import handle_callback

        mock_run.return_value = MagicMock(
            stdout="PR created: https://github.com/org/repo/pull/99",
            stderr="",
            returncode=0,
        )

        update = _make_callback_update("release_confirm")
        ctx = AsyncMock()

        await handle_callback(update, ctx)

        query = update.callback_query
        query.edit_message_text.assert_called()
        edited_text = query.edit_message_text.call_args[0][0]
        assert "PR" in edited_text or "✓" in edited_text

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.subprocess.run")
    @pytest.mark.asyncio
    async def test_confirm_failure_shows_error(self, mock_run):
        """If release.py fails, error should be shown."""
        from bot import handle_callback

        mock_run.return_value = MagicMock(
            stdout="",
            stderr="fatal: not a git repo",
            returncode=1,
        )

        update = _make_callback_update("release_confirm")
        ctx = AsyncMock()

        await handle_callback(update, ctx)

        query = update.callback_query
        query.edit_message_text.assert_called()
        edited_text = query.edit_message_text.call_args[0][0]
        assert "⚠️" in edited_text or "失敗" in edited_text


class TestReleaseCallbackCancel:
    """Clicking cancel button should dismiss without running release."""

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.subprocess.run")
    @pytest.mark.asyncio
    async def test_cancel_does_not_run_release(self, mock_run):
        """release_cancel should not execute release.py."""
        from bot import handle_callback

        update = _make_callback_update("release_cancel")
        ctx = AsyncMock()

        await handle_callback(update, ctx)

        mock_run.assert_not_called()

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_cancel_edits_message(self):
        """Cancel should edit message to show cancellation."""
        from bot import handle_callback

        update = _make_callback_update("release_cancel")
        ctx = AsyncMock()

        await handle_callback(update, ctx)

        query = update.callback_query
        query.edit_message_text.assert_called()
