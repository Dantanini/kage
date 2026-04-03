"""Tests for /plan command — session plan read/write/consume."""

from datetime import date
from pathlib import Path

import pytest

from plan import PlanStore


class TestPlanStore:
    """Test plan file management."""

    @pytest.fixture
    def store(self, tmp_path):
        return PlanStore(base_dir=str(tmp_path))

    def test_read_empty_when_no_file(self, store):
        assert store.read() == ""

    def test_write_creates_file(self, store):
        store.write("1. Define State interface\n2. Write tests")
        assert store.path.exists()

    def test_read_returns_content(self, store):
        store.write("Do the thing")
        assert "Do the thing" in store.read()

    def test_write_includes_date(self, store):
        store.write("task list")
        content = store.path.read_text(encoding="utf-8")
        assert date.today().isoformat() in content

    def test_append_adds_to_existing(self, store):
        store.write("First plan")
        store.append("Also do this")
        content = store.read()
        assert "First plan" in content
        assert "Also do this" in content

    def test_consume_returns_content_and_clears(self, store):
        store.write("Important plan")
        content = store.consume()
        assert "Important plan" in content
        assert store.read() == ""

    def test_consume_empty_returns_empty(self, store):
        assert store.consume() == ""

    def test_has_plan(self, store):
        assert store.has_plan() is False
        store.write("something")
        assert store.has_plan() is True

    def test_build_context_injection(self, store):
        store.write("1. Do X\n2. Do Y")
        injection = store.build_context_injection()
        assert "[下次 Session 計畫" in injection
        assert "Do X" in injection

    def test_build_context_injection_empty(self, store):
        assert store.build_context_injection() == ""

    def test_overwrite_replaces(self, store):
        store.write("Old plan")
        store.write("New plan")
        content = store.read()
        assert "New plan" in content
        assert "Old plan" not in content


class TestPlanInstructions:
    """Plan injection must include workflow instructions."""

    @pytest.fixture
    def store(self, tmp_path):
        return PlanStore(base_dir=str(tmp_path))

    def test_injection_contains_instructions(self, store):
        """Instructions section must be present when plan exists."""
        store.write("- [ ] Task 1")
        injection = store.build_context_injection()
        assert "## Instructions" in injection

    def test_injection_mentions_task_done(self, store):
        """Must remind model to call task_done.py."""
        store.write("- [ ] Task 1")
        injection = store.build_context_injection()
        assert "task_done" in injection

    def test_injection_mentions_no_direct_pr(self, store):
        """Must remind model not to open PR directly."""
        store.write("- [ ] Task 1")
        injection = store.build_context_injection()
        assert "PR" in injection

    def test_injection_mentions_develop(self, store):
        """Must remind model to branch from develop."""
        store.write("- [ ] Task 1")
        injection = store.build_context_injection()
        assert "develop" in injection

    def test_injection_mentions_branch_check(self, store):
        """Must remind model to verify branch before commit."""
        store.write("- [ ] Task 1")
        injection = store.build_context_injection()
        assert "git branch" in injection

    def test_injection_contains_user_tasks(self, store):
        """User's tasks must appear in the injection."""
        store.write("- [ ] Add login page\n- [ ] Fix logout bug")
        injection = store.build_context_injection()
        assert "Add login page" in injection
        assert "Fix logout bug" in injection

    def test_write_preserves_user_content_only(self, store):
        """write() stores user content, instructions added at injection time."""
        store.write("- [ ] My task")
        raw = store.path.read_text(encoding="utf-8")
        # Raw file has user content
        assert "My task" in raw
        # Instructions are added at injection, not in the file
        # (so user editing the file doesn't see boilerplate)
