"""Tests for event-driven memory writer."""

from datetime import date
from pathlib import Path

import pytest

from memory import MemoryWriter, MemoryStore


def _make_structured_dir(tmp_path: Path) -> Path:
    """Create a structured memory directory with initial files."""
    mem_dir = tmp_path / "memory" / "kage-memory"
    mem_dir.mkdir(parents=True)
    (mem_dir / "active-tasks.md").write_text(
        "---\ntitle: Active Tasks\ntags: [tg-bot, memory, active]\n"
        f"updated: 2026-04-02\n---\n\n# Active Tasks\n\n"
        "## 待 Merge PR\n\n- PR #12 pdf-support\n",
        encoding="utf-8",
    )
    (mem_dir / "lessons-learned.md").write_text(
        "---\ntitle: Lessons Learned\ntags: [tg-bot, memory, system]\n"
        f"updated: 2026-04-02\n---\n\n# Lessons Learned\n\n"
        "## 操作教訓\n\n- Check log before saying ready\n",
        encoding="utf-8",
    )
    (mem_dir / "session-log.md").write_text(
        "---\ntitle: Session Log\ntags: [tg-bot, memory, system]\n"
        f"updated: 2026-04-02\n---\n\n# Session Log\n\n"
        "## 2026-04-02\n\nDid stuff\n",
        encoding="utf-8",
    )
    return tmp_path


class TestMemoryWriter:
    """Test event-driven memory writes."""

    @pytest.fixture
    def base(self, tmp_path):
        return _make_structured_dir(tmp_path)

    @pytest.fixture
    def writer(self, base):
        store = MemoryStore(base_dir=str(base))
        return MemoryWriter(store)

    def test_write_lesson(self, writer, base):
        writer.write_lesson("Never force push to main")
        content = (base / "memory" / "kage-memory" / "lessons-learned.md").read_text()
        assert "Never force push to main" in content

    def test_write_lesson_updates_frontmatter_date(self, writer, base):
        writer.write_lesson("test lesson")
        content = (base / "memory" / "kage-memory" / "lessons-learned.md").read_text()
        assert f"updated: {date.today().isoformat()}" in content

    def test_write_task_update(self, writer, base):
        writer.write_task_update("PR #18 merged")
        content = (base / "memory" / "kage-memory" / "active-tasks.md").read_text()
        assert "PR #18 merged" in content

    def test_write_task_update_updates_date(self, writer, base):
        writer.write_task_update("test task")
        content = (base / "memory" / "kage-memory" / "active-tasks.md").read_text()
        assert f"updated: {date.today().isoformat()}" in content

    def test_write_session_summary(self, writer, base):
        writer.write_session_summary("Implemented structured memory")
        content = (base / "memory" / "kage-memory" / "session-log.md").read_text()
        assert "Implemented structured memory" in content
        assert f"## {date.today().isoformat()}" in content

    def test_write_session_summary_updates_date(self, writer, base):
        writer.write_session_summary("test summary")
        content = (base / "memory" / "kage-memory" / "session-log.md").read_text()
        assert f"updated: {date.today().isoformat()}" in content

    def test_no_crash_without_structured_dir(self, tmp_path):
        """Writer should not crash if structured dir doesn't exist."""
        store = MemoryStore(base_dir=str(tmp_path))
        writer = MemoryWriter(store)
        # These should be no-ops, not crashes
        writer.write_lesson("test")
        writer.write_task_update("test")
        writer.write_session_summary("test")

    def test_multiple_writes_append(self, writer, base):
        writer.write_lesson("Lesson 1")
        writer.write_lesson("Lesson 2")
        content = (base / "memory" / "kage-memory" / "lessons-learned.md").read_text()
        assert "Lesson 1" in content
        assert "Lesson 2" in content

    def test_write_does_not_duplicate_date_section(self, writer, base):
        """Multiple session writes on same day should use same date header."""
        writer.write_session_summary("First summary")
        writer.write_session_summary("Second summary")
        content = (base / "memory" / "kage-memory" / "session-log.md").read_text()
        today = date.today().isoformat()
        assert content.count(f"## {today}") == 1
