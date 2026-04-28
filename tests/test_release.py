"""Tests for release script — commit parsing and PR content generation."""

import sys
from unittest.mock import patch, MagicMock

import pytest

from release import parse_commits, generate_title, generate_body, get_commits_between


# --- Fixtures ---

SAMPLE_LOG = """\
abc1234 feat: add session lifecycle hook system
def5678 feat: add persistent memory layer
111aaaa fix: update REPOS["kage"] path from tg-bot to kage
222bbbb docs: update README with new architecture
333cccc ci: add GitHub Actions test workflow
444dddd chore: add one-click deploy script"""

SINGLE_FEAT = "aaa1111 feat: add dark mode toggle"

SINGLE_FIX = "bbb2222 fix: crash on empty message"


class TestParseCommits:
    """Parse git log --oneline output into structured commit data."""

    def test_parses_multiple_commits(self):
        commits = parse_commits(SAMPLE_LOG)
        assert len(commits) == 6

    def test_commit_structure(self):
        commits = parse_commits(SAMPLE_LOG)
        first = commits[0]
        assert first["hash"] == "abc1234"
        assert first["type"] == "feat"
        assert first["description"] == "add session lifecycle hook system"

    def test_commit_with_scope(self):
        log = "aaa1111 feat(session): add timeout handling"
        commits = parse_commits(log)
        assert commits[0]["type"] == "feat"
        assert commits[0]["scope"] == "session"
        assert commits[0]["description"] == "add timeout handling"

    def test_commit_without_scope(self):
        commits = parse_commits(SINGLE_FEAT)
        assert commits[0]["scope"] is None

    def test_non_conventional_commit(self):
        log = "ccc3333 random commit message without type"
        commits = parse_commits(log)
        assert commits[0]["type"] == "other"
        assert commits[0]["description"] == "random commit message without type"

    def test_empty_input(self):
        assert parse_commits("") == []

    def test_whitespace_only(self):
        assert parse_commits("   \n  \n  ") == []

    def test_merge_commit_skipped(self):
        log = "ddd4444 Merge pull request #5 from develop\neee5555 feat: real work"
        commits = parse_commits(log)
        assert len(commits) == 1
        assert commits[0]["hash"] == "eee5555"


class TestGenerateTitle:
    """Generate concise PR title from parsed commits."""

    def test_single_feat(self):
        commits = parse_commits(SINGLE_FEAT)
        title = generate_title(commits)
        assert "add dark mode toggle" in title.lower()

    def test_single_fix(self):
        commits = parse_commits(SINGLE_FIX)
        title = generate_title(commits)
        assert "fix" in title.lower()

    def test_multiple_commits_summary(self):
        commits = parse_commits(SAMPLE_LOG)
        title = generate_title(commits)
        # Should mention feat count since there are multiple
        assert "feat" in title.lower() or "feature" in title.lower()

    def test_title_length_under_72(self):
        commits = parse_commits(SAMPLE_LOG)
        title = generate_title(commits)
        assert len(title) <= 72

    def test_title_starts_with_release(self):
        commits = parse_commits(SAMPLE_LOG)
        title = generate_title(commits)
        assert title.lower().startswith("release:")


class TestGenerateBody:
    """Generate PR body with grouped changelog."""

    def test_contains_feat_section(self):
        commits = parse_commits(SAMPLE_LOG)
        body = generate_body(commits)
        assert "feat" in body.lower() or "feature" in body.lower()

    def test_contains_fix_section(self):
        commits = parse_commits(SAMPLE_LOG)
        body = generate_body(commits)
        assert "fix" in body.lower()

    def test_contains_commit_descriptions(self):
        commits = parse_commits(SAMPLE_LOG)
        body = generate_body(commits)
        assert "session lifecycle hook" in body.lower()
        assert "persistent memory layer" in body.lower()

    def test_single_commit_body(self):
        commits = parse_commits(SINGLE_FEAT)
        body = generate_body(commits)
        assert "dark mode toggle" in body.lower()

    def test_empty_commits(self):
        body = generate_body([])
        assert body == ""

    def test_groups_by_type(self):
        commits = parse_commits(SAMPLE_LOG)
        body = generate_body(commits)
        lines = body.split("\n")
        # Should have section headers
        headers = [l for l in lines if l.startswith("##")]
        assert len(headers) >= 2  # at least feat and fix sections


class TestGetCommitsBetween:
    """Ensure get_commits_between uses remote refs after fetch."""

    @patch("release.subprocess.run")
    def test_uses_origin_refs_by_default(self, mock_run):
        mock_run.return_value = MagicMock(stdout="abc1234 feat: something\n")
        get_commits_between()
        args = mock_run.call_args[0][0]
        assert "origin/main..origin/develop" in " ".join(args)

    @patch("release.subprocess.run")
    def test_custom_refs_include_origin_prefix(self, mock_run):
        mock_run.return_value = MagicMock(stdout="")
        get_commits_between(base="main", head="release")
        args = mock_run.call_args[0][0]
        assert "origin/main..origin/release" in " ".join(args)


class TestSyncDevelopWithMain:
    """sync_develop_with_main brings main's merge commit back into develop."""

    @patch("release.subprocess.run")
    def test_sync_runs_expected_git_commands(self, mock_run):
        from release import sync_develop_with_main
        mock_run.return_value = MagicMock(returncode=0)

        sync_develop_with_main()

        # Collect all commands run
        all_commands = [" ".join(c.args[0]) for c in mock_run.call_args_list]
        joined = " ; ".join(all_commands)

        # Must fetch, switch to develop, merge main, push
        assert "git fetch" in joined
        assert "git checkout develop" in joined or "git switch develop" in joined
        assert "git merge origin/main" in joined
        assert "git push" in joined

    @patch("release.subprocess.run")
    def test_sync_uses_check_true_so_failures_propagate(self, mock_run):
        from release import sync_develop_with_main
        mock_run.return_value = MagicMock(returncode=0)

        sync_develop_with_main()

        # Every subprocess.run call must have check=True so a merge conflict
        # or push failure is surfaced to the user, not silently swallowed.
        for call in mock_run.call_args_list:
            assert call.kwargs.get("check") is True, (
                f"sync subprocess call missing check=True: {call}"
            )


class TestMainSyncMode:
    """`python3 release.py --sync` runs sync, not PR creation."""

    @patch("release.create_pr")
    @patch("release.sync_develop_with_main")
    def test_sync_flag_calls_sync_only(self, mock_sync, mock_create):
        from release import main
        with patch.object(sys, "argv", ["release.py", "--sync"]):
            main()
        mock_sync.assert_called_once()
        mock_create.assert_not_called()

    @patch("release.subprocess.run")
    @patch("release.create_pr")
    @patch("release.get_commits_between")
    def test_default_mode_prints_sync_hint(self, mock_log, mock_create, mock_run, capsys):
        """After creating the PR, release.py must remind user how to sync."""
        from release import main
        mock_log.return_value = "abc1234 feat: x"
        mock_run.return_value = MagicMock(returncode=0)
        with patch.object(sys, "argv", ["release.py"]):
            main()
        out = capsys.readouterr().out
        assert "--sync" in out
