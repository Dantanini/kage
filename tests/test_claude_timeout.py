"""Tests for claude subprocess timeout — prevent bot from hanging indefinitely."""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


@pytest.fixture
def mock_claude_bin():
    """Patch _find_claude to return a fake path."""
    with patch("bot._find_claude", return_value="/usr/bin/claude"):
        yield


@pytest.fixture
def mock_env(mock_claude_bin):
    """Patch environment deps so _run_claude_once doesn't touch real state."""
    with patch("bot.memory_store") as mem, \
         patch("bot.plan_store") as plan, \
         patch("bot._current_repo", {"path": "/tmp/fake"}):
        mem.check_recovery_needed.return_value = ""
        mem.build_context_prefix.return_value = ""
        plan.build_context_injection.return_value = ""
        yield


class TestRunClaudeOnceTimeout:
    """_run_claude_once should respect CLAUDE_TIMEOUT_SECONDS."""

    @pytest.mark.asyncio
    async def test_normal_completion_returns_output(self, mock_env):
        """Claude finishes within timeout → return stdout."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"hello", b""))
        mock_proc.returncode = 0
        mock_proc.kill = MagicMock()

        with patch("bot.asyncio.create_subprocess_exec", return_value=mock_proc):
            from bot import _run_claude_once
            result = await _run_claude_once("test", "sonnet", "fake-id")
            assert result == "hello"
            mock_proc.kill.assert_not_called()

    @pytest.mark.asyncio
    async def test_timeout_raises_error(self, mock_env):
        """Claude exceeds timeout → should raise TimeoutError."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        with patch("bot.asyncio.create_subprocess_exec", return_value=mock_proc), \
             patch("bot.CLAUDE_TIMEOUT_SECONDS", 1):
            from bot import _run_claude_once
            with pytest.raises(asyncio.TimeoutError):
                await _run_claude_once("test", "sonnet", "fake-id")

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self, mock_env):
        """After timeout, the subprocess must be killed."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        with patch("bot.asyncio.create_subprocess_exec", return_value=mock_proc), \
             patch("bot.CLAUDE_TIMEOUT_SECONDS", 1):
            from bot import _run_claude_once
            with pytest.raises(asyncio.TimeoutError):
                await _run_claude_once("test", "sonnet", "fake-id")
            mock_proc.kill.assert_called_once()


class TestRunClaudeTimeoutRetry:
    """_run_claude should handle timeout in its retry loop."""

    @pytest.mark.asyncio
    async def test_timeout_triggers_retry_and_fails(self, mock_env):
        """Timeout on all attempts → return error message."""
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        with patch("bot.asyncio.create_subprocess_exec", return_value=mock_proc), \
             patch("bot.CLAUDE_TIMEOUT_SECONDS", 1), \
             patch("bot.asyncio.sleep", new_callable=AsyncMock):
            from bot import _run_claude
            result = await _run_claude("test", "sonnet", "fake-id")
            assert result.startswith("⚠️")

    @pytest.mark.asyncio
    async def test_timeout_then_success_on_retry(self, mock_env):
        """First attempt times out, second succeeds."""
        fail_proc = AsyncMock()
        fail_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
        fail_proc.kill = MagicMock()
        fail_proc.wait = AsyncMock()

        ok_proc = AsyncMock()
        ok_proc.communicate = AsyncMock(return_value=(b"success", b""))
        ok_proc.returncode = 0
        ok_proc.kill = MagicMock()

        call_count = 0

        async def fake_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return fail_proc if call_count == 1 else ok_proc

        with patch("bot.asyncio.create_subprocess_exec", side_effect=fake_exec), \
             patch("bot.CLAUDE_TIMEOUT_SECONDS", 1), \
             patch("bot.asyncio.sleep", new_callable=AsyncMock):
            from bot import _run_claude
            result = await _run_claude("test", "sonnet", "fake-id")
            assert result == "success"
