"""Tests for executor — worktree management + parallel execution."""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from executor import WorktreeManager, PlanExecutor, TaskResult


def run_async(coro):
    """Run async test without pytest-asyncio."""
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def repo_dir(tmp_path):
    """Create a fake git repo for testing."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    return tmp_path


@pytest.fixture
def wt_manager(repo_dir):
    return WorktreeManager(str(repo_dir))


@pytest.fixture
def executor(repo_dir):
    return PlanExecutor(
        repos={"kage": str(repo_dir), "journal": str(repo_dir)},
        run_claude=AsyncMock(return_value="done"),
        notify=AsyncMock(),
        max_parallel=3,
    )


class TestWorktreeManager:
    """Worktree create, cleanup, stale detection."""

    def test_worktree_dir(self, wt_manager, repo_dir):
        assert wt_manager.worktree_dir == Path(repo_dir) / ".worktrees"

    @patch("executor.subprocess.run")
    def test_create_worktree(self, mock_run, wt_manager):
        mock_run.return_value = MagicMock(returncode=0)
        path = wt_manager.create("feature/test-task")
        assert "feature-test-task" in str(path)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "worktree" in args
        assert "add" in args

    @patch("executor.subprocess.run")
    def test_remove_worktree(self, mock_run, wt_manager):
        mock_run.return_value = MagicMock(returncode=0)
        wt_path = wt_manager.worktree_dir / "feature-test"
        wt_path.mkdir(parents=True)
        wt_manager.remove(wt_path)
        assert mock_run.called

    @patch("executor.subprocess.run")
    def test_cleanup_stale(self, mock_run, wt_manager):
        mock_run.return_value = MagicMock(returncode=0)
        # Create fake stale worktrees
        wt_dir = wt_manager.worktree_dir
        wt_dir.mkdir(parents=True)
        (wt_dir / "stale-branch-1").mkdir()
        (wt_dir / "stale-branch-2").mkdir()
        removed = wt_manager.cleanup_stale()
        assert removed == 2

    def test_cleanup_stale_no_dir(self, wt_manager):
        removed = wt_manager.cleanup_stale()
        assert removed == 0


class TestTaskResult:
    """Task result data class."""

    def test_success(self):
        r = TaskResult(branch="feature/x", success=True, output="done", repo="kage")
        assert r.success
        assert r.branch == "feature/x"

    def test_failure(self):
        r = TaskResult(branch="feature/x", success=False, output="error", repo="kage")
        assert not r.success


class TestPlanExecutor:
    """Parallel and sequential task execution."""

    def test_execute_single_task(self, executor):
        async def _test():
            tasks = [{"branch": "feature/a", "prompt": "do A", "repo": "kage"}]
            results = await executor.execute_phase(tasks)
            assert len(results) == 1
            assert results[0].success
            executor._notify.assert_called_once()
        run_async(_test())

    def test_execute_parallel_different_repos(self, executor):
        async def _test():
            tasks = [
                {"branch": "feature/a", "prompt": "do A", "repo": "kage"},
                {"branch": "feature/b", "prompt": "do B", "repo": "journal"},
            ]
            results = await executor.execute_phase(tasks)
            assert len(results) == 2
            assert all(r.success for r in results)
        run_async(_test())

    def test_execute_sequential_same_repo(self, executor):
        """Same repo tasks should run sequentially."""
        async def _test():
            execution_order = []

            async def tracked_claude(prompt, model, session_id, **kwargs):
                execution_order.append(prompt)
                await asyncio.sleep(0.01)
                return "done"

            executor._run_claude = tracked_claude
            tasks = [
                {"branch": "feature/a", "prompt": "first", "repo": "kage"},
                {"branch": "feature/b", "prompt": "second", "repo": "kage"},
            ]
            results = await executor.execute_phase(tasks)
            assert len(results) == 2
            assert execution_order == ["first", "second"]
        run_async(_test())

    def test_execute_multi_phase(self, executor):
        async def _test():
            phases = [
                [
                    {"branch": "feature/a", "prompt": "phase 1 task a", "repo": "kage"},
                    {"branch": "feature/b", "prompt": "phase 1 task b", "repo": "journal"},
                ],
                [
                    {"branch": "feature/c", "prompt": "phase 2 task c", "repo": "kage"},
                ],
            ]
            all_results = await executor.execute_all(phases)
            assert len(all_results) == 2
            assert len(all_results[0]) == 2
            assert len(all_results[1]) == 1
        run_async(_test())

    def test_max_parallel_respected(self, executor):
        async def _test():
            executor._max_parallel = 2
            executor._semaphore = asyncio.Semaphore(2)
            concurrent_count = 0
            max_concurrent = 0

            async def tracked_claude(prompt, model, session_id, **kwargs):
                nonlocal concurrent_count, max_concurrent
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.05)
                concurrent_count -= 1
                return "done"

            executor._run_claude = tracked_claude
            tasks = [
                {"branch": f"feature/{i}", "prompt": f"task {i}", "repo": f"repo{i}"}
                for i in range(4)
            ]
            await executor.execute_phase(tasks)
            assert max_concurrent <= 2
        run_async(_test())

    def test_task_failure_doesnt_stop_others(self, executor):
        async def _test():
            call_count = 0

            async def failing_claude(prompt, model, session_id, **kwargs):
                nonlocal call_count
                call_count += 1
                if "fail" in prompt:
                    raise Exception("boom")
                return "done"

            executor._run_claude = failing_claude
            tasks = [
                {"branch": "feature/ok", "prompt": "ok task", "repo": "kage"},
                {"branch": "feature/fail", "prompt": "fail task", "repo": "journal"},
            ]
            results = await executor.execute_phase(tasks)
            assert len(results) == 2
            assert results[0].success
            assert not results[1].success
            assert call_count == 2
        run_async(_test())

    def test_notify_called_per_task(self, executor):
        async def _test():
            tasks = [
                {"branch": "feature/a", "prompt": "A", "repo": "kage"},
                {"branch": "feature/b", "prompt": "B", "repo": "journal"},
            ]
            await executor.execute_phase(tasks)
            assert executor._notify.call_count == 2
        run_async(_test())

    def test_pause_stops_execution(self, executor):
        async def _test():
            async def slow_claude(prompt, model, session_id, **kwargs):
                await asyncio.sleep(0.1)
                return "done"

            executor._run_claude = slow_claude
            phases = [
                [{"branch": "feature/a", "prompt": "A", "repo": "kage"}],
                [{"branch": "feature/b", "prompt": "B", "repo": "kage"}],
            ]

            async def run_and_pause():
                task = asyncio.create_task(executor.execute_all(phases))
                await asyncio.sleep(0.05)
                executor.pause()
                return await task

            results = await run_and_pause()
            assert len(results) == 1
            assert executor.paused
        run_async(_test())
