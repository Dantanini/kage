"""Tests: memory save hook refuses to write when dev-journal is on a feature
branch or has a dirty working tree.

Without this guard, end-of-session memory updates would be appended to whatever
branch happens to be checked out, mixing memory edits with in-progress work.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_subprocess(returncode=0, stdout=b"", stderr=b""):
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


def _make_session(qa_log=None):
    session = MagicMock()
    session.qa_log = qa_log if qa_log is not None else [("q1", "a1")]
    return session


class TestCheckJournalSafe:
    """_check_journal_safe_for_memory_save returns (ok, reason)."""

    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_main_clean_is_safe(self, mock_subprocess):
        from bot import _check_journal_safe_for_memory_save

        # branch check returns "main", status returns empty
        mock_subprocess.side_effect = [
            _make_subprocess(stdout=b"main\n"),
            _make_subprocess(stdout=b""),
        ]

        ok, reason = await _check_journal_safe_for_memory_save("/path/to/journal")

        assert ok is True
        assert reason == ""

    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_feature_branch_is_unsafe(self, mock_subprocess):
        from bot import _check_journal_safe_for_memory_save

        mock_subprocess.side_effect = [
            _make_subprocess(stdout=b"feature/foo\n"),
        ]

        ok, reason = await _check_journal_safe_for_memory_save("/path/to/journal")

        assert ok is False
        assert "feature/foo" in reason
        assert "main" in reason.lower()

    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_main_with_dirty_working_tree_is_unsafe(self, mock_subprocess):
        from bot import _check_journal_safe_for_memory_save

        mock_subprocess.side_effect = [
            _make_subprocess(stdout=b"main\n"),
            _make_subprocess(stdout=b" M memory/notes.md\n?? newfile.md\n"),
        ]

        ok, reason = await _check_journal_safe_for_memory_save("/path/to/journal")

        assert ok is False
        assert "memory/notes.md" in reason or "newfile" in reason or "dirty" in reason.lower()

    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_git_branch_command_failure_is_unsafe(self, mock_subprocess):
        from bot import _check_journal_safe_for_memory_save

        mock_subprocess.side_effect = [
            _make_subprocess(returncode=128, stderr=b"fatal: not a git repository"),
        ]

        ok, reason = await _check_journal_safe_for_memory_save("/path/to/journal")

        assert ok is False
        assert "not a git repository" in reason or "fail" in reason.lower()


class TestMemorySaveHookGuard:
    """Hook short-circuits when journal is unsafe; proceeds when clean on main."""

    @patch("bot.send_telegram_message")
    @patch("bot._run_claude", new_callable=AsyncMock)
    @patch("bot._check_journal_safe_for_memory_save", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_hook_aborts_when_journal_unsafe(
        self, mock_check, mock_run_claude, mock_send
    ):
        from bot import _make_memory_save_hook

        mock_check.return_value = (False, "not on main (current: feature/foo)")
        hook = _make_memory_save_hook()

        await hook(_make_session())

        mock_run_claude.assert_not_called()
        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][0]
        assert "feature/foo" in sent_text or "main" in sent_text
        assert "跳過" in sent_text or "skip" in sent_text.lower() or "⚠" in sent_text

    @patch("bot.send_telegram_message")
    @patch("bot._run_claude", new_callable=AsyncMock)
    @patch("bot._check_journal_safe_for_memory_save", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_hook_proceeds_when_journal_safe(
        self, mock_check, mock_run_claude, mock_send
    ):
        from bot import _make_memory_save_hook

        mock_check.return_value = (True, "")
        mock_run_claude.return_value = "ok"
        hook = _make_memory_save_hook()

        await hook(_make_session())

        mock_run_claude.assert_called_once()

    @patch("bot.send_telegram_message")
    @patch("bot._run_claude", new_callable=AsyncMock)
    @patch("bot._check_journal_safe_for_memory_save", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_hook_skips_check_when_qa_log_empty(
        self, mock_check, mock_run_claude, mock_send
    ):
        """Empty qa_log means nothing to save; no need to check or warn."""
        from bot import _make_memory_save_hook

        hook = _make_memory_save_hook()

        await hook(_make_session(qa_log=[]))

        mock_check.assert_not_called()
        mock_run_claude.assert_not_called()
        mock_send.assert_not_called()
