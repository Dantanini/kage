"""Tests for /clone command — usage / already-registered / success / failure paths."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_update(text: str, user_id: int = 123):
    update = AsyncMock()
    update.effective_user = MagicMock(id=user_id)
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


class TestCmdClone:
    @patch("bot._check_auth", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_unauthorized_user_silently_ignored(self, mock_auth):
        mock_auth.return_value = False
        from bot import cmd_clone

        update = _make_update("/clone https://example.com/r.git")
        await cmd_clone(update, AsyncMock())

        update.message.reply_text.assert_not_called()

    @patch("bot.ADMIN_ID", 123)
    @pytest.mark.asyncio
    async def test_missing_url_shows_usage(self):
        from bot import cmd_clone

        update = _make_update("/clone")
        await cmd_clone(update, AsyncMock())

        update.message.reply_text.assert_called_once()
        msg = update.message.reply_text.call_args[0][0]
        assert "用法" in msg
        assert "/clone" in msg

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.repo_registry")
    @pytest.mark.asyncio
    async def test_already_registered_repo_rejected(self, mock_registry):
        from bot import cmd_clone

        mock_registry.get_path.return_value = "/home/x/repos/myrepo"
        update = _make_update("/clone https://github.com/u/myrepo.git")

        await cmd_clone(update, AsyncMock())

        msg = update.message.reply_text.call_args[0][0]
        assert "已存在" in msg
        assert "myrepo" in msg
        mock_registry.add.assert_not_called()

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.REPOS", {})
    @patch("bot.clone_repo")
    @patch("bot.repo_registry")
    @pytest.mark.asyncio
    async def test_successful_clone_registers_and_replies(
        self, mock_registry, mock_clone
    ):
        from bot import cmd_clone, REPOS

        mock_registry.get_path.return_value = None
        mock_clone.return_value = "/home/x/repos/myrepo"
        update = _make_update("/clone https://github.com/u/myrepo.git")

        await cmd_clone(update, AsyncMock())

        mock_clone.assert_called_once()
        mock_registry.add.assert_called_once_with("myrepo", "/home/x/repos/myrepo")
        assert REPOS["myrepo"] == "/home/x/repos/myrepo"

        replies = [c.args[0] for c in update.message.reply_text.call_args_list]
        assert any("clone" in r.lower() for r in replies)
        assert any("✅" in r and "myrepo" in r for r in replies)

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.clone_repo")
    @patch("bot.repo_registry")
    @pytest.mark.asyncio
    async def test_clone_failure_reported_to_user(self, mock_registry, mock_clone):
        from bot import cmd_clone

        mock_registry.get_path.return_value = None
        mock_clone.side_effect = RuntimeError("git: connection refused")
        update = _make_update("/clone https://github.com/u/r.git")

        await cmd_clone(update, AsyncMock())

        replies = [c.args[0] for c in update.message.reply_text.call_args_list]
        fail_msg = next((r for r in replies if "❌" in r), None)
        assert fail_msg is not None
        assert "connection refused" in fail_msg
        mock_registry.add.assert_not_called()

    @patch("bot.ADMIN_ID", 123)
    @patch("bot.REPOS", {})
    @patch("bot.clone_repo")
    @patch("bot.repo_registry")
    @pytest.mark.asyncio
    async def test_custom_name_overrides_inferred_repo_name(
        self, mock_registry, mock_clone
    ):
        from bot import cmd_clone

        mock_registry.get_path.return_value = None
        mock_clone.return_value = "/home/x/repos/aliased"
        update = _make_update("/clone https://github.com/u/myrepo.git aliased")

        await cmd_clone(update, AsyncMock())

        mock_registry.add.assert_called_once()
        added_name = mock_registry.add.call_args[0][0]
        assert added_name == "aliased"
