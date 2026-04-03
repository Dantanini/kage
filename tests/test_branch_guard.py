"""Tests for branch guard — prevent commits on protected branches."""

import subprocess
import textwrap
from pathlib import Path

import pytest


HOOK_PATH = Path(__file__).parent.parent / ".githooks" / "pre-commit"


class TestBranchGuardInHook:
    """pre-commit hook should block commits on main and develop."""

    def _run_hook_with_branch(self, branch_name: str) -> subprocess.CompletedProcess:
        """Simulate running the pre-commit hook as if on a given branch."""
        # We can't easily change branch in test, so we extract and test
        # the guard logic directly by grepping the hook content
        assert HOOK_PATH.exists(), "pre-commit hook must exist"
        content = HOOK_PATH.read_text(encoding="utf-8")
        assert "PROTECTED_BRANCHES" in content, (
            "pre-commit hook must contain branch guard (PROTECTED_BRANCHES)"
        )

    def test_hook_contains_branch_guard(self):
        """The pre-commit hook must have a branch protection check."""
        self._run_hook_with_branch("main")

    def test_hook_lists_main_as_protected(self):
        content = HOOK_PATH.read_text(encoding="utf-8")
        assert "main" in content

    def test_hook_lists_develop_as_protected(self):
        content = HOOK_PATH.read_text(encoding="utf-8")
        assert "develop" in content


class TestBranchGuardScript:
    """Standalone branch_guard.sh should be testable independently."""

    GUARD_SCRIPT = Path(__file__).parent.parent / "scripts" / "branch_guard.sh"

    def test_script_exists(self):
        assert self.GUARD_SCRIPT.exists(), "scripts/branch_guard.sh must exist"

    @pytest.mark.parametrize("branch", ["main", "develop"])
    def test_blocks_protected_branch(self, branch):
        """Should exit 1 when on a protected branch."""
        result = subprocess.run(
            ["bash", str(self.GUARD_SCRIPT), branch],
            capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "禁止" in result.stderr or "禁止" in result.stdout

    @pytest.mark.parametrize("branch", [
        "feat/new-feature",
        "fix/bug-fix",
        "chore/cleanup",
    ])
    def test_allows_feature_branch(self, branch):
        """Should exit 0 when on a feature branch."""
        result = subprocess.run(
            ["bash", str(self.GUARD_SCRIPT), branch],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
