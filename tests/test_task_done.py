"""Tests for scripts/task_done.py — branch completion notification.

NOTE: This test loads a standalone script via open()+exec().
The script source is cached at collection time to survive other tests
that may alter the git working tree (e.g. test_restart_pull doing
git checkout main).
"""

import types
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

SCRIPT_PATH = (Path(__file__).parent.parent / "scripts" / "task_done.py").resolve()

# Cache source at import/collection time — before other tests can change the tree
_SOURCE_CACHE: str | None = None


def _read_source() -> str:
    global _SOURCE_CACHE
    if _SOURCE_CACHE is None:
        _SOURCE_CACHE = SCRIPT_PATH.read_text()
    return _SOURCE_CACHE


# Eagerly read source at collection time
_read_source()


def _load_task_done():
    """Load task_done module from cached source, bypassing filesystem."""
    mod = types.ModuleType("task_done")
    mod.__file__ = str(SCRIPT_PATH)
    code = compile(_read_source(), str(SCRIPT_PATH), "exec")
    exec(code, mod.__dict__)
    return mod


@pytest.fixture
def task_done():
    """Import task_done module fresh each test."""
    yield _load_task_done()


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

    def test_sends_with_reply_markup(self, task_done):
        import json

        with patch.object(task_done.urllib.request, "urlopen") as mock_urlopen:
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
            body = json.loads(req.data)
            assert "reply_markup" in body
            assert body["chat_id"] == 123

    def test_returns_true_on_success(self, task_done):
        with patch.object(task_done.urllib.request, "urlopen") as mock_urlopen:
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
