"""Tests for release script — commit parsing and PR content generation."""

import pytest

from release import parse_commits, generate_title, generate_body


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
