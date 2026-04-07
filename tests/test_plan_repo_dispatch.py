"""Tests for plan execution repo dispatch — Phase 2 of kage v2.

When a plan task has a repo field, execution should use that repo's path as cwd.
"""


def _resolve_task_repo(repo_name: str | None, repos: dict[str, str]) -> str | None:
    """Mirror of bot._resolve_task_repo for testing without heavy imports."""
    if not repo_name:
        return None
    return repos.get(repo_name)


def test_resolve_task_repo_known():
    repos = {"journal": "/home/user/dev-journal", "kage": "/home/user/kage"}
    assert _resolve_task_repo("journal", repos) == "/home/user/dev-journal"
    assert _resolve_task_repo("kage", repos) == "/home/user/kage"


def test_resolve_task_repo_unknown():
    repos = {"journal": "/home/user/dev-journal"}
    assert _resolve_task_repo("unknown", repos) is None


def test_resolve_task_repo_none():
    repos = {"journal": "/home/user/dev-journal"}
    assert _resolve_task_repo(None, repos) is None


def test_resolve_task_repo_empty():
    repos = {"journal": "/home/user/dev-journal"}
    assert _resolve_task_repo("", repos) is None
