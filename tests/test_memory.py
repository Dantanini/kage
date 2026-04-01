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
