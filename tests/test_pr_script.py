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

    def test_noninteractive_adds_fill(self):
        """When stdin is not a TTY (non-interactive), --fill should be added."""
        content = PR_SCRIPT.read_text(encoding="utf-8")
        assert "! -t 0" in content or "--fill" in content, \
            "pr.sh must detect non-interactive mode and add --fill"

    def test_noninteractive_detection_logic(self):
        """Script should check if stdin is a TTY and add --fill accordingly."""
        content = PR_SCRIPT.read_text(encoding="utf-8")
        # TTY check must exist and be before the exec line
        assert "! -t 0" in content
        # The non-interactive block should add --fill to GH_ARGS
        lines = content.split("\n")
        found_tty_check = False
        found_fill_after = False
        for line in lines:
            if "! -t 0" in line:
                found_tty_check = True
            if found_tty_check and "--fill" in line and "GH_ARGS" in line:
                found_fill_after = True
                break
        assert found_fill_after, "Must add --fill to GH_ARGS after TTY check"
