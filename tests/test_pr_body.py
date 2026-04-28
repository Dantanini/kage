"""Tests for scripts/pr_body.py — auto-generate PR description from commits + diff."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Load pr_body module from scripts/
spec = importlib.util.spec_from_file_location(
    "pr_body", Path(__file__).resolve().parent.parent / "scripts" / "pr_body.py"
)


def _load_module():
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestGenerateBody:
    """generate_body uses the project's standard PR template."""

    @patch("subprocess.run")
    def test_includes_summary_section(self, mock_run):
        pr_body = _load_module()
        # log, diff --stat, diff --name-only (test files)
        mock_run.side_effect = [
            MagicMock(stdout="- fix: add foo\n- fix: add bar\n", returncode=0),
            MagicMock(stdout=" foo.py | 5 +++++\n bar.py | 3 +++\n", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        body = pr_body.generate_body()

        assert "## Summary" in body
        assert "fix: add foo" in body
        assert "fix: add bar" in body

    @patch("subprocess.run")
    def test_includes_diff_stats_section(self, mock_run):
        pr_body = _load_module()
        mock_run.side_effect = [
            MagicMock(stdout="- fix: x\n", returncode=0),
            MagicMock(stdout=" foo.py | 5 +++++\n 1 file changed, 5 insertions(+)\n", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        body = pr_body.generate_body()

        assert "## Diff stats" in body
        assert "foo.py" in body

    @patch("subprocess.run")
    def test_includes_test_plan_section(self, mock_run):
        pr_body = _load_module()
        mock_run.side_effect = [
            MagicMock(stdout="- fix: x\n", returncode=0),
            MagicMock(stdout=" foo.py | 1 +\n", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        body = pr_body.generate_body()

        assert "## Test plan" in body
        assert "[ ] CI passes" in body

    @patch("subprocess.run")
    def test_test_plan_counts_test_files_when_changed(self, mock_run):
        pr_body = _load_module()
        mock_run.side_effect = [
            MagicMock(stdout="- fix: x\n", returncode=0),
            MagicMock(stdout=" foo.py | 1 +\n", returncode=0),
            MagicMock(stdout="tests/test_foo.py\ntests/test_bar.py\n", returncode=0),
        ]

        body = pr_body.generate_body()

        assert "2 test file(s) changed" in body

    @patch("subprocess.run")
    def test_test_plan_says_no_test_changes_when_none(self, mock_run):
        pr_body = _load_module()
        mock_run.side_effect = [
            MagicMock(stdout="- docs: x\n", returncode=0),
            MagicMock(stdout=" README.md | 1 +\n", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        body = pr_body.generate_body()

        assert "no test changes" in body

    @patch("subprocess.run")
    def test_includes_claude_code_attribution(self, mock_run):
        pr_body = _load_module()
        mock_run.side_effect = [
            MagicMock(stdout="- x\n", returncode=0),
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        body = pr_body.generate_body()

        assert "Claude Code" in body
        assert "claude.com/claude-code" in body

    @patch("subprocess.run")
    def test_handles_no_commits(self, mock_run):
        pr_body = _load_module()
        mock_run.side_effect = [
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        body = pr_body.generate_body()

        # Should still produce a Test plan + attribution
        assert "## Test plan" in body
        assert "Claude Code" in body

    @patch("subprocess.run")
    def test_uses_origin_develop_by_default(self, mock_run):
        pr_body = _load_module()
        mock_run.side_effect = [
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        pr_body.generate_body()

        first_call_args = " ".join(mock_run.call_args_list[0].args[0])
        assert "origin/develop..HEAD" in first_call_args

    @patch("subprocess.run")
    def test_diff_uses_triple_dot_so_stale_branch_does_not_appear_to_revert(self, mock_run):
        """diff stats must use `A...HEAD` (merge-base) not `A..HEAD`."""
        pr_body = _load_module()
        mock_run.side_effect = [
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        pr_body.generate_body()

        diff_call_args = " ".join(mock_run.call_args_list[1].args[0])
        assert "origin/develop...HEAD" in diff_call_args

    @patch("subprocess.run")
    def test_custom_base_ref(self, mock_run):
        pr_body = _load_module()
        mock_run.side_effect = [
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]

        pr_body.generate_body(base_ref="origin/main")

        first_call_args = " ".join(mock_run.call_args_list[0].args[0])
        assert "origin/main..HEAD" in first_call_args


class TestCli:
    """Running pr_body.py as a CLI prints the generated body to stdout."""

    def test_runs_as_script(self, tmp_path):
        """Smoke test: pr_body.py runs and prints something (in current repo)."""
        script = Path(__file__).resolve().parent.parent / "scripts" / "pr_body.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, cwd=str(script.parent.parent),
        )
        # Even if no commits / no remote, exit 0 with something printed
        assert result.returncode == 0
