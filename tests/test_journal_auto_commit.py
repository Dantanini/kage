"""Tests: kage auto-commits dev-journal changes after a session or workflow ends.

Without this, files Claude writes to dev-journal (interview practice, daily
notes, etc.) sit in working tree and get lost on next /restart.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_subprocess(returncode=0, stdout=b"", stderr=b""):
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


def _make_session(session_id="abcdef12345", qa_log=None):
    session = MagicMock()
    session.session_id = session_id
    session.qa_log = qa_log if qa_log is not None else [("q1", "a1")]
    return session


class TestCommitJournalChanges:
    """_commit_journal_session_changes runs commit.py only when on main."""

    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_main_branch_success(self, mock_subprocess):
        from bot import _commit_journal_session_changes

        mock_subprocess.side_effect = [
            _make_subprocess(stdout=b"main\n"),
            _make_subprocess(stdout="已推送到遠端\n已推送到備份".encode()),
        ]

        ok, info = await _commit_journal_session_changes("/path", "msg")

        assert ok is True
        assert "推送" in info or "ok" in info.lower()

    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_main_branch_no_changes(self, mock_subprocess):
        from bot import _commit_journal_session_changes

        mock_subprocess.side_effect = [
            _make_subprocess(stdout=b"main\n"),
            _make_subprocess(stdout="沒有變更需要 commit".encode()),
        ]

        ok, info = await _commit_journal_session_changes("/path", "msg")

        assert ok is True
        assert "沒有變更" in info

    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_feature_branch_refuses(self, mock_subprocess):
        from bot import _commit_journal_session_changes

        mock_subprocess.side_effect = [
            _make_subprocess(stdout=b"feature/foo\n"),
        ]

        ok, info = await _commit_journal_session_changes("/path", "msg")

        assert ok is False
        assert "feature/foo" in info or "main" in info.lower()
        # Must NOT have invoked commit.py
        assert mock_subprocess.call_count == 1

    @patch("bot.asyncio.create_subprocess_exec", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_commit_script_fails(self, mock_subprocess):
        from bot import _commit_journal_session_changes

        mock_subprocess.side_effect = [
            _make_subprocess(stdout=b"main\n"),
            _make_subprocess(returncode=1, stderr=b"pre-commit hook blocked: secret detected"),
        ]

        ok, info = await _commit_journal_session_changes("/path", "msg")

        assert ok is False
        assert "secret" in info or "fail" in info.lower() or "blocked" in info


class TestCommitJournalHook:
    """End hook auto-commits journal after session memory save."""

    @patch("bot.send_telegram_message")
    @patch("bot._commit_journal_session_changes", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_success_notifies_user(self, mock_commit, mock_send):
        from bot import _make_commit_journal_hook

        mock_commit.return_value = (True, "已推送到遠端")
        hook = _make_commit_journal_hook()

        await hook(_make_session())

        mock_commit.assert_called_once()
        mock_send.assert_called_once()
        sent = mock_send.call_args[0][0]
        assert "✅" in sent or "commit" in sent.lower()

    @patch("bot.send_telegram_message")
    @patch("bot._commit_journal_session_changes", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_no_changes_silent(self, mock_commit, mock_send):
        from bot import _make_commit_journal_hook

        mock_commit.return_value = (True, "沒有變更需要 commit")
        hook = _make_commit_journal_hook()

        await hook(_make_session())

        mock_commit.assert_called_once()
        mock_send.assert_not_called()

    @patch("bot.send_telegram_message")
    @patch("bot._commit_journal_session_changes", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_failure_warns_user(self, mock_commit, mock_send):
        from bot import _make_commit_journal_hook

        mock_commit.return_value = (False, "not on main (current: feature/foo)")
        hook = _make_commit_journal_hook()

        await hook(_make_session())

        mock_send.assert_called_once()
        sent = mock_send.call_args[0][0]
        assert "feature/foo" in sent or "失敗" in sent or "⚠" in sent


class TestCommitHookRegistered:
    """Commit journal hook must be wired up to session end hooks."""

    @pytest.mark.asyncio
    async def test_commit_hook_in_end_hooks(self):
        """sessions._end_hook_factories should include the commit hook factory."""
        import bot

        # Find a hook factory that, when invoked, returns something whose
        # source contains a call to _commit_journal_session_changes.
        import inspect
        found = False
        for factory in bot.sessions._end_hook_factories:
            hook_obj = factory()
            try:
                src = inspect.getsource(hook_obj)
            except (TypeError, OSError):
                continue
            if "_commit_journal_session_changes" in src:
                found = True
                break

        assert found, "commit-journal hook not registered as session end hook"
