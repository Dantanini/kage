"""Tests for scripts/task_done.py — branch completion notification."""

from unittest.mock import patch, MagicMock
import importlib
import sys
from pathlib import Path

import pytest

# Import the module under test
SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))


@pytest.fixture
def task_done():
    """Import task_done module fresh each test."""
    if "task_done" in sys.modules:
        del sys.modules["task_done"]
    import task_done
    yield task_done


class TestBuildMessage:
    """Test notification message formatting."""

    def test_includes_branch_name(self, task_done):
        msg = task_done.build_message(
            branch="feat/branch-guard",
            summary="pre-commit hook 擋 main/develop commit",
            tests=["test_blocks_main", "test_blocks_develop"],
            prevents="在 main 上直接 commit",
        )
        assert "feat/branch-guard" in msg

    def test_includes_summary(self, task_done):
        msg = task_done.build_message(
            branch="feat/x",
            summary="加了新功能",
            tests=["test_a"],
            prevents="壞事",
        )
        assert "加了新功能" in msg

    def test_includes_all_test_items(self, task_done):
        tests = ["test_blocks_main", "test_allows_feature", "test_hook_exists"]
        msg = task_done.build_message(
            branch="feat/x",
            summary="guard",
            tests=tests,
            prevents="commit on main",
        )
        for t in tests:
            assert t in msg

    def test_includes_prevents(self, task_done):
        msg = task_done.build_message(
            branch="feat/x",
            summary="s",
            tests=["t"],
            prevents="PR 開到 main",
        )
        assert "PR 開到 main" in msg


class TestBuildKeyboard:
    """Test inline keyboard structure."""

    def test_has_two_buttons(self, task_done):
        kb = task_done.build_keyboard("feat/x")
        buttons = kb["inline_keyboard"][0]
        assert len(buttons) == 2

    def test_first_button_is_open_pr(self, task_done):
        kb = task_done.build_keyboard("feat/x")
        btn = kb["inline_keyboard"][0][0]
        assert "PR" in btn["text"]
        assert "task_pr:" in btn["callback_data"]
        assert "feat/x" in btn["callback_data"]

    def test_second_button_is_ask(self, task_done):
        kb = task_done.build_keyboard("feat/x")
        btn = kb["inline_keyboard"][0][1]
        assert "追問" in btn["text"]
        assert "task_ask:" in btn["callback_data"]
        assert "feat/x" in btn["callback_data"]

    def test_callback_data_under_64_bytes(self, task_done):
        """Telegram callback_data limit is 64 bytes."""
        long_branch = "feat/very-long-branch-name-that-is-quite-long"
        kb = task_done.build_keyboard(long_branch)
        for row in kb["inline_keyboard"]:
            for btn in row:
                assert len(btn["callback_data"].encode("utf-8")) <= 64


class TestSendNotification:
    """Test the send function calls Telegram API correctly."""

    @patch("task_done.urllib.request.urlopen")
    def test_sends_with_reply_markup(self, mock_urlopen, task_done):
        mock_urlopen.return_value = MagicMock()
        task_done.send_task_done(
            branch="feat/x",
            summary="s",
            tests=["t1"],
            prevents="p",
            token="fake-token",
            chat_id="123",
        )
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        import json
        body = json.loads(req.data)
        assert "reply_markup" in body
        assert body["chat_id"] == 123

    @patch("task_done.urllib.request.urlopen")
    def test_returns_true_on_success(self, mock_urlopen, task_done):
        mock_urlopen.return_value = MagicMock()
        result = task_done.send_task_done(
            branch="feat/x", summary="s", tests=["t"], prevents="p",
            token="t", chat_id="1",
        )
        assert result is True

    def test_returns_false_on_missing_token(self, task_done):
        result = task_done.send_task_done(
            branch="feat/x", summary="s", tests=["t"], prevents="p",
            token="", chat_id="1",
        )
        assert result is False
