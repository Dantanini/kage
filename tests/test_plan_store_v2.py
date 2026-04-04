"""Tests for PlanStore v2 — three-section plan management."""

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

    def test_append_goes_to_draft_section(self, plan_store):
        plan_store.append("task 1")
        assert "## 待整理" in plan_store.read()
        assert "task 1" in plan_store.read()

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

    def test_set_planned_clears_draft(self, plan_store):
        plan_store.append("raw idea")
        plan_store.set_planned("- [ ] refined task")
        content = plan_store.read()
        assert "## 待整理" not in content
        assert "raw idea" not in content

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

    def test_complete_item_moves_to_completed(self, plan_store):
        plan_store.append("task")
        plan_store.set_planned("- [ ] task A\n- [ ] task B")
        plan_store.set_executing()
        plan_store.complete_item("task A")
        content = plan_store.read()
        assert "## 已完成" in content
        assert "- [x] task A" in content

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

    def test_draft_items(self, plan_store):
        plan_store.append("idea 1")
        plan_store.append("idea 2")
        drafts = plan_store.draft_items()
        assert len(drafts) == 2


class TestThreeSections:
    """Three sections coexist: 待整理 / 已規劃 / 已完成."""

    def test_append_after_planned_adds_to_draft(self, plan_store):
        plan_store.append("original idea")
        plan_store.set_planned("- [ ] planned task")
        plan_store.append("new idea")
        content = plan_store.read()
        assert "## 待整理" in content
        assert "new idea" in content
        assert "## 已規劃" in content
        assert "planned task" in content

    def test_all_three_sections(self, plan_store):
        plan_store.append("draft item")
        plan_store.set_planned("- [ ] task A\n- [ ] task B")
        plan_store.set_executing()
        plan_store.complete_item("task A")
        plan_store.pause()
        plan_store.append("another idea")
        content = plan_store.read()
        assert "## 已規劃" in content
        assert "## 已完成" in content
        assert "## 待整理" in content


class TestDelete:
    """Delete items by index."""

    def test_delete_draft_item(self, plan_store):
        plan_store.append("keep this")
        plan_store.append("delete this")
        items = plan_store.all_items_numbered()
        assert len(items) == 2
        deleted = plan_store.delete_item(2)
        assert "delete this" in deleted
        assert "delete this" not in plan_store.read()
        assert "keep this" in plan_store.read()

    def test_delete_returns_none_for_invalid_index(self, plan_store):
        plan_store.append("item")
        assert plan_store.delete_item(99) is None

    def test_delete_last_item_resets_to_empty(self, plan_store):
        plan_store.append("only item")
        plan_store.delete_item(1)
        assert plan_store.status == PlanStatus.EMPTY

    def test_all_items_numbered(self, plan_store):
        plan_store.append("draft 1")
        plan_store.append("draft 2")
        plan_store.set_planned("- [ ] planned 1")
        plan_store.set_executing()
        plan_store.complete_item("planned 1")
        plan_store.pause()
        plan_store.append("draft 3")
        items = plan_store.all_items_numbered()
        assert len(items) >= 2


class TestArchive:
    """Archive completed items, keep pending."""

    def test_archive_creates_full_snapshot(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.archive_completed()
        archive_dir = Path(plan_store._local_dir) / "plan" / "archive"
        files = list(archive_dir.iterdir())
        assert len(files) == 1
        archive_content = files[0].read_text(encoding="utf-8")
        assert "A" in archive_content

    def test_archive_removes_completed_section(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.archive_completed()
        content = plan_store.read()
        assert "## 已完成" not in content

    def test_archive_all_resets_to_empty(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.archive_completed()
        assert plan_store.status == PlanStatus.EMPTY


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
