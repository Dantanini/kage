"""Tests for PlanStore v2 — pure file-based, no LLM."""

import pytest
from pathlib import Path
from plan_v2 import PlanStore, PlanStatus


@pytest.fixture
def plan_store(tmp_path):
    return PlanStore(local_dir=str(tmp_path / ".local"))


class TestPlanLifecycle:
    """Plan file lifecycle: create, append, read, archive."""

    def test_initial_state_is_empty(self, plan_store):
        assert plan_store.status == PlanStatus.EMPTY
        assert plan_store.read() == ""
        assert not plan_store.has_plan()

    def test_append_creates_plan(self, plan_store):
        plan_store.append("買菜清單要更新")
        assert plan_store.has_plan()
        assert plan_store.status == PlanStatus.DRAFT
        assert "買菜清單要更新" in plan_store.read()

    def test_append_multiple(self, plan_store):
        plan_store.append("task 1: 改 README")
        plan_store.append("task 2: 改 CLAUDE.md")
        content = plan_store.read()
        assert "task 1" in content
        assert "task 2" in content

    def test_append_preserves_order(self, plan_store):
        plan_store.append("first")
        plan_store.append("second")
        plan_store.append("third")
        content = plan_store.read()
        assert content.index("first") < content.index("second") < content.index("third")

    def test_set_planned(self, plan_store):
        plan_store.append("some task")
        plan_store.set_planned("## Phase 1\n- [ ] do thing A\n- [ ] do thing B")
        assert plan_store.status == PlanStatus.PLANNED
        assert "Phase 1" in plan_store.read()

    def test_set_planned_without_draft_raises(self, plan_store):
        with pytest.raises(ValueError, match="沒有草稿"):
            plan_store.set_planned("plan content")

    def test_mark_executing(self, plan_store):
        plan_store.append("task")
        plan_store.set_planned("- [ ] do it")
        plan_store.set_executing()
        assert plan_store.status == PlanStatus.EXECUTING

    def test_mark_executing_without_plan_raises(self, plan_store):
        with pytest.raises(ValueError, match="沒有計畫"):
            plan_store.set_executing()

    def test_complete_item(self, plan_store):
        plan_store.append("task")
        plan_store.set_planned("- [ ] task A\n- [ ] task B")
        plan_store.set_executing()
        plan_store.complete_item("task A")
        content = plan_store.read()
        assert "- [x] task A" in content
        assert "- [ ] task B" in content

    def test_all_completed(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B")
        plan_store.set_executing()
        assert not plan_store.all_completed()
        plan_store.complete_item("A")
        assert not plan_store.all_completed()
        plan_store.complete_item("B")
        assert plan_store.all_completed()

    def test_pending_items(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B\n- [ ] C")
        plan_store.set_executing()
        plan_store.complete_item("A")
        pending = plan_store.pending_items()
        assert len(pending) == 2
        assert "B" in pending[0]
        assert "C" in pending[1]


class TestArchive:
    """Archive completed items, keep pending."""

    def test_archive_completed(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B")
        plan_store.set_executing()
        plan_store.complete_item("A")
        archived = plan_store.archive_completed()
        assert "A" in archived
        # current should only have B
        content = plan_store.read()
        assert "- [x] A" not in content
        assert "- [ ] B" in content

    def test_archive_all_resets_to_empty(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.archive_completed()
        assert plan_store.status == PlanStatus.EMPTY

    def test_archive_file_created(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.archive_completed()
        archive_dir = Path(plan_store._local_dir) / "plan" / "archive"
        assert any(archive_dir.iterdir())


class TestPause:
    """Pause execution, resume later."""

    def test_pause_sets_status_back_to_planned(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.pause()
        assert plan_store.status == PlanStatus.PLANNED

    def test_resume_from_pause(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.pause()
        # Resume
        plan_store.set_executing()
        pending = plan_store.pending_items()
        assert len(pending) == 1
        assert "B" in pending[0]


class TestContextInjection:
    """Build prompt context for Claude."""

    def test_empty_plan_returns_empty_context(self, plan_store):
        assert plan_store.build_context_injection() == ""

    def test_draft_returns_draft_context(self, plan_store):
        plan_store.append("改 README")
        ctx = plan_store.build_context_injection()
        assert "改 README" in ctx

    def test_planned_returns_instructions(self, plan_store):
        plan_store.append("task")
        plan_store.set_planned("- [ ] do it")
        ctx = plan_store.build_context_injection()
        assert "feature branch" in ctx
        assert "do it" in ctx
