"""Tests for context injection behaviour in _run_claude_once.

Plan context (planned.md / draft.md) should only be injected when
inject_plan=True is passed — i.e. interactive chat sessions.  All other
callers (workflows, course, note, task-execute, background tasks) use the
default inject_plan=False so they don't receive stale/irrelevant plan content.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

import bot
from plan_v2 import PlanStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc(stdout: bytes = b"ok", returncode: int = 0):
    proc = AsyncMock()
    proc.communicate = AsyncMock(return_value=(stdout, b""))
    proc.returncode = returncode
    return proc


# ---------------------------------------------------------------------------
# _run_claude_once — inject_plan flag
# ---------------------------------------------------------------------------

class TestRunClauceOnceInjectPlan:

    @pytest.fixture(autouse=True)
    def _patch_deps(self, tmp_path, monkeypatch):
        """Patch external calls so tests run without a real claude binary."""
        monkeypatch.setattr(bot, "_find_claude", lambda: "/usr/bin/claude")

        # Memory prefix — return empty to keep assertions simple
        monkeypatch.setattr(
            bot.memory_store, "check_recovery_needed", lambda _: ""
        )
        monkeypatch.setattr(
            bot.memory_store, "build_context_prefix", lambda: ""
        )

        # Use a real PlanStore backed by a temp directory
        store = PlanStore(local_dir=str(tmp_path))
        monkeypatch.setattr(bot, "plan_store", store)
        self.store = store

    @patch("bot.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_inject_plan_false_skips_plan_context(self, mock_exec):
        """inject_plan=False → planned.md content NOT in the prompt sent to Claude."""
        self.store.append("重要任務")
        self.store.set_planned("- [ ] 重要任務")

        mock_exec.return_value = _make_proc()

        await bot._run_claude_once("hello", "sonnet", "sid-1", resume=False, inject_plan=False)

        _, kwargs = mock_exec.call_args
        stdin_input = kwargs.get("stdin") or mock_exec.call_args[1].get("stdin")
        proc = mock_exec.return_value
        sent_bytes = proc.communicate.call_args[1].get("input") or proc.communicate.call_args[0][0]
        sent = sent_bytes.decode()

        assert "重要任務" not in sent

    @patch("bot.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_inject_plan_true_includes_plan_context(self, mock_exec):
        """inject_plan=True → planned.md content IS in the prompt sent to Claude."""
        self.store.append("重要任務")
        self.store.set_planned("- [ ] 重要任務")

        mock_exec.return_value = _make_proc()

        await bot._run_claude_once("hello", "sonnet", "sid-2", resume=False, inject_plan=True)

        proc = mock_exec.return_value
        sent = proc.communicate.call_args[1].get("input") or proc.communicate.call_args[0][0]
        if isinstance(sent, bytes):
            sent = sent.decode()

        assert "重要任務" in sent

    @patch("bot.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_inject_plan_true_empty_plan_adds_nothing(self, mock_exec):
        """inject_plan=True with empty plan → no plan section added."""
        # store is empty by default
        mock_exec.return_value = _make_proc()

        await bot._run_claude_once("hi", "sonnet", "sid-3", resume=False, inject_plan=True)

        proc = mock_exec.return_value
        sent = proc.communicate.call_args[1].get("input") or proc.communicate.call_args[0][0]
        if isinstance(sent, bytes):
            sent = sent.decode()

        assert "Session 計畫" not in sent
        assert "計畫草稿" not in sent

    @patch("bot.asyncio.create_subprocess_exec")
    @pytest.mark.asyncio
    async def test_resume_never_injects_plan(self, mock_exec):
        """resume=True skips prefix injection entirely, regardless of inject_plan."""
        self.store.append("任務A")
        self.store.set_planned("- [ ] 任務A")

        mock_exec.return_value = _make_proc()

        await bot._run_claude_once("hi", "sonnet", "sid-4", resume=True, inject_plan=True)

        proc = mock_exec.return_value
        sent = proc.communicate.call_args[1].get("input") or proc.communicate.call_args[0][0]
        if isinstance(sent, bytes):
            sent = sent.decode()

        # resume=True → no prefix injected
        assert "任務A" not in sent
        assert "[系統]" not in sent
