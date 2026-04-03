"""Tests for memory module."""

import tempfile
from pathlib import Path

import pytest

from memory import MemoryStore


class TestMemoryStore:
    """Test persistent memory read/write."""

    @pytest.fixture
    def store(self, tmp_path):
        return MemoryStore(base_dir=str(tmp_path))

    def test_exists_false_when_no_file(self, store):
        assert store.exists() is False

    def test_read_returns_empty_when_no_file(self, store):
        assert store.read() == ""

    def test_context_prefix_empty_when_no_memory(self, store):
        assert store.build_context_prefix() == ""

    def test_read_returns_content(self, store):
        store.path.write_text("## 2026-04-01\n- learned hooks", encoding="utf-8")
        content = store.read()
        assert "learned hooks" in content

    def test_read_truncates_long_content(self, store):
        long_text = "x" * 5000
        store.path.write_text(long_text, encoding="utf-8")
        content = store.read(limit=200)
        assert len(content) <= 220  # 200 + truncation marker
        assert "truncated" in content

    def test_context_prefix_wraps_content(self, store):
        store.path.write_text("some memory", encoding="utf-8")
        prefix = store.build_context_prefix()
        assert prefix.startswith("[持久記憶")
        assert "some memory" in prefix
        assert prefix.endswith("[/持久記憶]\n\n")

    def test_build_save_prompt_empty_for_no_pairs(self, store):
        assert store.build_save_prompt([]) == ""

    def test_build_save_prompt_includes_qa(self, store):
        pairs = [("what is hooks?", "hooks are lifecycle callbacks")]
        prompt = store.build_save_prompt(pairs)
        assert "what is hooks?" in prompt
        assert "lifecycle callbacks" in prompt
        assert str(store.path) in prompt

    def test_build_save_prompt_limits_pairs(self, store):
        pairs = [(f"q{i}", f"a{i}") for i in range(10)]
        prompt = store.build_save_prompt(pairs, max_pairs=3)
        # Should only include last 3
        assert "q7" in prompt
        assert "q8" in prompt
        assert "q9" in prompt
        assert "q0" not in prompt

    def test_memory_dir_created_automatically(self, tmp_path):
        store = MemoryStore(base_dir=str(tmp_path / "nonexistent"))
        assert store.path.parent.exists()


class TestStructuredMemory:
    """Test structured memory directory support (active-tasks, lessons-learned, session-log)."""

    @pytest.fixture
    def structured_dir(self, tmp_path):
        """Create a memory/kage-memory/ directory with structured files."""
        mem_dir = tmp_path / "memory" / "kage-memory"
        mem_dir.mkdir(parents=True)
        (mem_dir / "active-tasks.md").write_text(
            "---\ntitle: Active Tasks\ntags: [tg-bot]\nupdated: 2026-04-03\n---\n\n"
            "# Active Tasks\n\n- PR #12 pdf-support\n- PR #13 pattern detector\n",
            encoding="utf-8",
        )
        (mem_dir / "lessons-learned.md").write_text(
            "---\ntitle: Lessons\ntags: [tg-bot]\nupdated: 2026-04-03\n---\n\n"
            "# Lessons\n\n- Check log before saying ready\n",
            encoding="utf-8",
        )
        (mem_dir / "session-log.md").write_text(
            "---\ntitle: Session Log\ntags: [tg-bot]\nupdated: 2026-04-03\n---\n\n"
            "# Session Log\n\n## 2026-04-02\n\nDid stuff\n",
            encoding="utf-8",
        )
        return tmp_path

    def test_read_structured_merges_all_files(self, structured_dir):
        store = MemoryStore(base_dir=str(structured_dir))
        content = store.read()
        assert "PR #12" in content
        assert "Check log" in content
        assert "2026-04-02" in content

    def test_read_structured_strips_frontmatter(self, structured_dir):
        store = MemoryStore(base_dir=str(structured_dir))
        content = store.read()
        assert "---" not in content
        assert "updated:" not in content

    def test_read_structured_respects_limit(self, structured_dir):
        store = MemoryStore(base_dir=str(structured_dir))
        content = store.read(limit=50)
        assert len(content) <= 70  # 50 + truncation marker

    def test_read_structured_falls_back_to_single_file(self, tmp_path):
        """If kage-memory/ dir doesn't exist but kage-memory.md does, use the file."""
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir(parents=True)
        (mem_dir / "kage-memory.md").write_text("## old format\n- legacy content\n")
        store = MemoryStore(base_dir=str(tmp_path))
        content = store.read()
        assert "legacy content" in content

    def test_read_structured_prefers_dir_over_file(self, structured_dir):
        """If both dir and file exist, prefer the directory."""
        (structured_dir / "memory" / "kage-memory.md").write_text("old single file")
        store = MemoryStore(base_dir=str(structured_dir))
        content = store.read()
        assert "PR #12" in content
        assert "old single file" not in content

    def test_build_save_prompt_references_structured_dir(self, structured_dir):
        store = MemoryStore(base_dir=str(structured_dir))
        prompt = store.build_save_prompt([("q", "a")])
        assert "session-log.md" in prompt

    def test_context_prefix_works_with_structured(self, structured_dir):
        store = MemoryStore(base_dir=str(structured_dir))
        prefix = store.build_context_prefix()
        assert "[持久記憶" in prefix
        assert "PR #12" in prefix


class TestRecoveryDetection:
    """Test abnormal exit detection via .needs_recovery marker."""

    @pytest.fixture
    def store(self, tmp_path):
        return MemoryStore(base_dir=str(tmp_path))

    @pytest.fixture
    def marker(self, tmp_path):
        return tmp_path / ".needs_recovery"

    def test_no_marker_returns_empty(self, store, marker):
        assert store.check_recovery_needed(marker) == ""

    def test_marker_exists_returns_warning(self, store, marker):
        marker.touch()
        result = store.check_recovery_needed(marker)
        assert "異常中斷" in result

    def test_marker_deleted_after_check(self, store, marker):
        marker.touch()
        store.check_recovery_needed(marker)
        assert not marker.exists()

    def test_marker_only_triggers_once(self, store, marker):
        marker.touch()
        first = store.check_recovery_needed(marker)
        second = store.check_recovery_needed(marker)
        assert "異常中斷" in first
        assert second == ""

    def test_warning_starts_with_system_tag(self, store, marker):
        marker.touch()
        result = store.check_recovery_needed(marker)
        assert result.startswith("[系統提示]")

    def test_exception_during_processing_returns_empty(self, store, marker):
        """If unlink fails (e.g. permission denied), catch and return empty."""
        marker.touch()
        from unittest.mock import patch
        with patch.object(type(marker), "unlink", side_effect=PermissionError("denied")):
            result = store.check_recovery_needed(marker)
        assert result == ""
