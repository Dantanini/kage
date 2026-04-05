"""Tests for plan execution cwd — task repo field should control working directory."""

from unittest.mock import AsyncMock, patch, MagicMock
import pytest


def _mock_plan_store(pending_items, parsed_items):
    store = MagicMock()
    store.pending_items.return_value = pending_items
    store.parse_planned_items.return_value = parsed_items
    store.read_completed.return_value = ""
    store.all_completed.return_value = False
    store.complete_item = MagicMock()
    return store


class TestPlanExecuteCwd:
    """_run_next_plan_item should pass correct cwd based on task repo field."""

    @pytest.mark.asyncio
    async def test_kage_repo_uses_kage_path(self):
        """Task with repo: kage → _run_claude called with cwd=kage path."""
        store = _mock_plan_store(
            ["- [ ] update CLAUDE.md"],
            [{"task": "update CLAUDE.md", "branch": "feat/x", "repo": "kage"}],
        )

        with patch("bot.plan_store", store), \
             patch("bot._run_claude", new_callable=AsyncMock, return_value="done") as mock_claude, \
             patch("bot.REPOS", {"journal": "/tmp/journal", "kage": "/tmp/kage", "home": "/tmp"}):
            from bot import _run_next_plan_item
            ctx = AsyncMock()
            ctx.bot = AsyncMock()
            await _run_next_plan_item(123, ctx)

            assert mock_claude.call_args.kwargs.get("cwd") == "/tmp/kage", \
                f"Expected cwd='/tmp/kage', got {mock_claude.call_args}"

    @pytest.mark.asyncio
    async def test_journal_repo_uses_journal_path(self):
        """Task with repo: journal → _run_claude called with cwd=journal path."""
        store = _mock_plan_store(
            ["- [ ] update daily"],
            [{"task": "update daily", "branch": None, "repo": "journal"}],
        )

        with patch("bot.plan_store", store), \
             patch("bot._run_claude", new_callable=AsyncMock, return_value="done") as mock_claude, \
             patch("bot.REPOS", {"journal": "/tmp/journal", "kage": "/tmp/kage", "home": "/tmp"}):
            from bot import _run_next_plan_item
            ctx = AsyncMock()
            ctx.bot = AsyncMock()
            await _run_next_plan_item(123, ctx)

            assert mock_claude.call_args.kwargs.get("cwd") == "/tmp/journal", \
                f"Expected cwd='/tmp/journal', got {mock_claude.call_args}"

    @pytest.mark.asyncio
    async def test_no_repo_uses_no_cwd_override(self):
        """Task without repo field → cwd not set (uses _run_claude default)."""
        store = _mock_plan_store(
            ["- [ ] do something"],
            [{"task": "do something", "branch": None, "repo": None}],
        )

        with patch("bot.plan_store", store), \
             patch("bot._run_claude", new_callable=AsyncMock, return_value="done") as mock_claude:
            from bot import _run_next_plan_item
            ctx = AsyncMock()
            ctx.bot = AsyncMock()
            await _run_next_plan_item(123, ctx)

            assert mock_claude.call_args.kwargs.get("cwd") is None, \
                f"Expected cwd=None, got {mock_claude.call_args}"
