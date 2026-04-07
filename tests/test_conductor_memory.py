"""Tests for conductor memory layer — Phase 0 of kage v2.

The conductor needs broader awareness of dev-journal's knowledge base,
beyond just kage-memory/. This includes:
- INDEX.md (global index — what's in the knowledge base)
- log.md (recent operations — what happened lately)
"""

from pathlib import Path

from memory import MemoryStore


def _make_journal(tmp_path: Path) -> Path:
    """Create a minimal dev-journal structure with INDEX.md and log.md."""
    journal = tmp_path / "journal"
    journal.mkdir()

    # Standard kage-memory (existing behavior)
    mem_dir = journal / "memory" / "kage-memory"
    mem_dir.mkdir(parents=True)
    (mem_dir / "active-tasks.md").write_text(
        "---\ntitle: Active Tasks\ntags: [memory]\nupdated: 2026-04-07\n---\n\n"
        "## PR Status\n\n- PR #75 open (pending v2)\n",
        encoding="utf-8",
    )

    # INDEX.md at repo root
    (journal / "INDEX.md").write_text(
        "# dev-journal index\n\n"
        "## Projects\n"
        "| projects/kage-v2-conductor.md | kage v2 plan |\n"
        "| projects/time-loop-game-design.md | game design |\n\n"
        "## Wiki\n"
        "| wiki/concepts/design-over-discipline.md | core philosophy |\n",
        encoding="utf-8",
    )

    # log.md at repo root (append-only, newest at bottom)
    (journal / "log.md").write_text(
        "# Operation Log\n\n"
        "## [2026-04-06] docs | dev-journal restructure plan\n"
        "## [2026-04-06] docs | karpathy notes\n"
        "## [2026-04-07] refactor | Phase 0 cleanup\n"
        "## [2026-04-07] refactor | Phase 1 global index\n"
        "## [2026-04-07] refactor | Phase 2 memory unification\n"
        "## [2026-04-07] refactor | Phase 3 structure\n"
        "## [2026-04-07] feat | Phase 4 automation\n",
        encoding="utf-8",
    )

    return journal


def test_read_global_context_includes_index(tmp_path):
    """Global context should include INDEX.md content."""
    journal = _make_journal(tmp_path)
    store = MemoryStore(base_dir=str(journal))
    ctx = store.read_global_context()
    assert "kage-v2-conductor" in ctx
    assert "design-over-discipline" in ctx


def test_read_global_context_includes_recent_log(tmp_path):
    """Global context should include recent log entries."""
    journal = _make_journal(tmp_path)
    store = MemoryStore(base_dir=str(journal))
    ctx = store.read_global_context()
    assert "Phase 4 automation" in ctx


def test_read_global_context_limits_log_lines(tmp_path):
    """Log should be truncated to max_log_lines."""
    journal = _make_journal(tmp_path)
    store = MemoryStore(base_dir=str(journal))
    ctx = store.read_global_context(max_log_lines=3)
    # Should have the 3 most recent entries
    assert "Phase 4 automation" in ctx
    assert "Phase 3 structure" in ctx
    assert "Phase 2 memory" in ctx
    # Should NOT have older entries
    assert "karpathy notes" not in ctx


def test_read_global_context_missing_files(tmp_path):
    """Should return empty string if INDEX.md and log.md don't exist."""
    journal = tmp_path / "empty-journal"
    journal.mkdir()
    (journal / "memory").mkdir()
    store = MemoryStore(base_dir=str(journal))
    ctx = store.read_global_context()
    assert ctx == ""


def test_build_context_prefix_includes_global(tmp_path):
    """build_context_prefix should include both kage-memory and global context."""
    journal = _make_journal(tmp_path)
    store = MemoryStore(base_dir=str(journal))
    prefix = store.build_context_prefix()
    # Should have kage-memory content
    assert "PR #75" in prefix
    # Should have global context
    assert "kage-v2-conductor" in prefix
