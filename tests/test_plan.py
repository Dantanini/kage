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
