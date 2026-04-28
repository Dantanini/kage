"""Tests for scripts/pr.sh — enforce PR base is always develop."""

import subprocess
from pathlib import Path

import pytest

PR_SCRIPT = Path(__file__).parent.parent / "scripts" / "pr.sh"


class TestPrScript:
    """pr.sh must enforce --base develop and block PRs from protected branches."""

    def test_script_exists(self):
        assert PR_SCRIPT.exists(), "scripts/pr.sh must exist"

    def test_script_is_executable(self):
        assert PR_SCRIPT.stat().st_mode & 0o111, "scripts/pr.sh must be executable"

    def test_contains_base_develop(self):
        """Script must hardcode --base develop."""
        content = PR_SCRIPT.read_text(encoding="utf-8")
        assert "--base develop" in content

    def test_blocks_pr_from_main(self):
        """Should refuse to open PR when on main branch."""
        result = subprocess.run(
            ["bash", str(PR_SCRIPT), "--dry-run", "--branch", "main"],
            capture_output=True, text=True,
        )
        assert result.returncode == 1
        assert "禁止" in result.stdout or "禁止" in result.stderr

    def test_blocks_pr_from_develop(self):
        """Should refuse to open PR from develop (develop→develop makes no sense)."""
        result = subprocess.run(
            ["bash", str(PR_SCRIPT), "--dry-run", "--branch", "develop"],
            capture_output=True, text=True,
        )
        assert result.returncode == 1

    def test_allows_feature_branch(self):
        """Should proceed (dry-run) on a feature branch."""
        result = subprocess.run(
            ["bash", str(PR_SCRIPT), "--dry-run", "--branch", "feat/test"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "--base develop" in result.stdout

    def test_auto_body_when_none_provided(self):
        """Script must call pr_body.py to generate a body when caller didn't pass --body."""
        content = PR_SCRIPT.read_text(encoding="utf-8")
        assert "pr_body.py" in content, \
            "pr.sh must invoke pr_body.py to generate PR description"
        assert "--body" in content

    def test_skips_auto_body_when_user_passes_body(self):
        """Script must detect --body / --body-file / --fill and skip auto generation."""
        content = PR_SCRIPT.read_text(encoding="utf-8")
        # All three opt-out flags must be checked
        assert "--body" in content
        assert "--body-file" in content
        assert "--fill" in content

    def test_auto_title_from_first_commit(self):
        """Script must auto-derive --title from the first commit on the branch."""
        content = PR_SCRIPT.read_text(encoding="utf-8")
        assert "--title" in content
        # Must use git log to derive title
        assert "git log" in content

    def test_aborts_when_pr_body_fails(self):
        """pr.sh must hard-exit if pr_body.py returns non-zero (sensitive content)."""
        content = PR_SCRIPT.read_text(encoding="utf-8")
        # Must check exit status of pr_body.py and abort, not swallow the error
        assert "exit 2" in content or "exit 1" in content
        # Must not have the old "|| echo" fallback that hid errors
        assert "auto body generation failed" not in content
