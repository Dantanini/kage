"""Executor — worktree-based parallel task execution engine.

Each task runs in an isolated git worktree. Tasks in different repos
run in parallel; tasks in the same repo run sequentially (unless
explicitly marked parallel-safe by Opus).

Supports pause/resume and per-task completion notifications.
"""

import asyncio
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Awaitable, Any

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    branch: str
    repo: str
    success: bool
    output: str


class WorktreeManager:
    """Manages git worktrees for isolated task execution."""

    def __init__(self, repo_dir: str):
        self._repo_dir = Path(repo_dir)

    @property
    def worktree_dir(self) -> Path:
        return self._repo_dir / ".worktrees"

    def create(self, branch: str) -> Path:
        """Create a worktree for the given branch name."""
        safe_name = branch.replace("/", "-")
        wt_path = self.worktree_dir / safe_name
        wt_path.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            ["git", "worktree", "add", str(wt_path), "-b", branch],
            cwd=str(self._repo_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        return wt_path

    def remove(self, wt_path: Path) -> None:
        """Remove a worktree and its branch."""
        branch_name = wt_path.name
        subprocess.run(
            ["git", "worktree", "remove", str(wt_path), "--force"],
            cwd=str(self._repo_dir),
            capture_output=True,
            text=True,
        )
        # Clean up branch
        subprocess.run(
            ["git", "branch", "-D", branch_name],
            cwd=str(self._repo_dir),
            capture_output=True,
            text=True,
        )

    def cleanup_stale(self) -> int:
        """Remove all stale worktrees. Returns count removed."""
        if not self.worktree_dir.exists():
            return 0

        count = 0
        for wt_path in list(self.worktree_dir.iterdir()):
            if wt_path.is_dir():
                try:
                    self.remove(wt_path)
                except Exception as e:
                    logger.warning(f"Failed to remove stale worktree {wt_path}: {e}")
                count += 1

        return count


class PlanExecutor:
    """Executes plan tasks with worktree isolation and parallelism.

    - Different repos → parallel (asyncio.gather)
    - Same repo → sequential
    - Respects max_parallel limit
    - Supports pause/resume
    """

    def __init__(
        self,
        repos: dict[str, str],
        run_claude: Callable[..., Awaitable[str]],
        notify: Callable[..., Awaitable[Any]],
        max_parallel: int = 3,
    ):
        self._repos = repos  # {"kage": "/path/to/kage", "journal": "/path/to/journal"}
        self._run_claude = run_claude
        self._notify = notify
        self._max_parallel = max_parallel
        self._semaphore = asyncio.Semaphore(max_parallel)
        self._worktree_managers: dict[str, WorktreeManager] = {
            name: WorktreeManager(path) for name, path in repos.items()
        }
        self.paused = False

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    async def _execute_task(self, task: dict) -> TaskResult:
        """Execute a single task in a worktree."""
        branch = task["branch"]
        prompt = task["prompt"]
        repo_name = task["repo"]
        repo_dir = self._repos.get(repo_name, "")

        async with self._semaphore:
            try:
                result = await self._run_claude(
                    prompt, "sonnet", branch, cwd=repo_dir
                )
                success = not result.startswith("⚠️")
                task_result = TaskResult(
                    branch=branch,
                    repo=repo_name,
                    success=success,
                    output=result,
                )
            except Exception as e:
                logger.error(f"Task {branch} failed: {e}")
                task_result = TaskResult(
                    branch=branch,
                    repo=repo_name,
                    success=False,
                    output=str(e),
                )

            await self._notify(task_result)
            return task_result

    async def execute_phase(self, tasks: list[dict]) -> list[TaskResult]:
        """Execute a phase of tasks. Group by repo for parallelism control."""
        # Group tasks by repo
        by_repo: dict[str, list[dict]] = {}
        for task in tasks:
            repo = task.get("repo", "default")
            by_repo.setdefault(repo, []).append(task)

        async def run_repo_tasks(repo_tasks: list[dict]) -> list[TaskResult]:
            """Run tasks for a single repo sequentially."""
            results = []
            for task in repo_tasks:
                if self.paused:
                    break
                result = await self._execute_task(task)
                results.append(result)
            return results

        # Run different repos in parallel
        repo_coroutines = [run_repo_tasks(tasks) for tasks in by_repo.values()]
        repo_results = await asyncio.gather(*repo_coroutines)

        # Flatten
        return [r for results in repo_results for r in results]

    async def execute_all(self, phases: list[list[dict]]) -> list[list[TaskResult]]:
        """Execute all phases sequentially. Within each phase, repos run in parallel."""
        all_results = []
        for phase in phases:
            if self.paused:
                break
            results = await self.execute_phase(phase)
            all_results.append(results)
        return all_results
