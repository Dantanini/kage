"""Tests for PlanStore v2 — three-file plan management."""

import pytest
from pathlib import Path
from plan_v2 import PlanStore, PlanStatus


@pytest.fixture
def plan_store(tmp_path):
    return PlanStore(local_dir=str(tmp_path / ".local"))


class TestPlanLifecycle:

    def test_initial_state_is_empty(self, plan_store):
        assert plan_store.status == PlanStatus.EMPTY
        assert not plan_store.has_plan()

    def test_append_creates_draft(self, plan_store):
        plan_store.append("買菜清單要更新")
        assert plan_store.has_plan()
        assert plan_store.status == PlanStatus.DRAFT
        assert "買菜清單要更新" in plan_store.read_draft()

    def test_append_multiple(self, plan_store):
        plan_store.append("task 1")
        plan_store.append("task 2")
        draft = plan_store.read_draft()
        assert "task 1" in draft
        assert "task 2" in draft

    def test_append_preserves_order(self, plan_store):
        plan_store.append("first")
        plan_store.append("second")
        plan_store.append("third")
        draft = plan_store.read_draft()
        assert draft.index("first") < draft.index("second") < draft.index("third")

    def test_set_planned(self, plan_store):
        plan_store.append("some task")
        plan_store.set_planned("- [ ] do thing A\n- [ ] do thing B")
        assert plan_store.status == PlanStatus.PLANNED
        assert "do thing A" in plan_store.read_planned()

    def test_set_planned_clears_draft(self, plan_store):
        plan_store.append("raw idea")
        plan_store.set_planned("- [ ] refined task")
        assert plan_store.read_draft() == ""

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
        assert "- [x] task A" in plan_store.read_completed()
        assert "task A" not in plan_store.read_planned()
        assert "task B" in plan_store.read_planned()

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

    def test_draft_items(self, plan_store):
        plan_store.append("idea 1")
        plan_store.append("idea 2")
        drafts = plan_store.draft_items()
        assert len(drafts) == 2


class TestThreeFiles:
    """Three files coexist: draft.md / planned.md / completed.md."""

    def test_append_after_planned(self, plan_store):
        plan_store.append("original idea")
        plan_store.set_planned("- [ ] planned task")
        plan_store.append("new idea")
        assert "new idea" in plan_store.read_draft()
        assert "planned task" in plan_store.read_planned()

    def test_all_three_files_populated(self, plan_store):
        plan_store.append("draft item")
        plan_store.set_planned("- [ ] task A\n- [ ] task B")
        plan_store.set_executing()
        plan_store.complete_item("task A")
        plan_store.pause()
        plan_store.append("another idea")
        assert plan_store.read_draft() != ""
        assert plan_store.read_planned() != ""
        assert plan_store.read_completed() != ""

    def test_files_are_separate(self, plan_store):
        """Each section is its own file, no cross-contamination."""
        plan_store.append("draft only")
        plan_store.set_planned("- [ ] planned only")
        assert "draft only" not in plan_store.read_planned()
        assert "planned only" not in plan_store.read_draft()


class TestDelete:

    def test_delete_draft_item(self, plan_store):
        plan_store.append("keep this")
        plan_store.append("delete this")
        items = plan_store.all_items_numbered()
        assert len(items) == 2
        deleted = plan_store.delete_item(2)
        assert "delete this" in deleted
        assert "delete this" not in plan_store.read_draft()

    def test_delete_returns_none_for_invalid_index(self, plan_store):
        plan_store.append("item")
        assert plan_store.delete_item(99) is None

    def test_delete_last_item_resets_to_empty(self, plan_store):
        plan_store.append("only item")
        plan_store.delete_item(1)
        assert plan_store.status == PlanStatus.EMPTY

    def test_all_items_numbered_across_files(self, plan_store):
        plan_store.append("draft 1")
        plan_store.set_planned("- [ ] planned 1")
        plan_store.set_executing()
        plan_store.complete_item("planned 1")
        plan_store.pause()
        plan_store.append("draft 2")
        items = plan_store.all_items_numbered()
        assert len(items) >= 2


class TestArchive:

    def test_archive_creates_snapshot_dir(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.archive_completed()
        archive_dir = Path(plan_store._local_dir) / "plan" / "archive"
        subdirs = [d for d in archive_dir.iterdir() if d.is_dir()]
        assert len(subdirs) == 1

    def test_archive_clears_completed(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.archive_completed()
        assert plan_store.read_completed() == ""

    def test_archive_all_resets_to_empty(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.archive_completed()
        assert plan_store.status == PlanStatus.EMPTY

    def test_archive_preserves_pending(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.archive_completed()
        assert "B" in plan_store.read_planned()


class TestPause:

    def test_pause_sets_status_back_to_planned(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B")
        plan_store.set_executing()
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


class TestContextInjection:

    def test_empty_returns_empty(self, plan_store):
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

    def test_planned_context_does_not_include_completed(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.pause()
        ctx = plan_store.build_context_injection()
        assert "- [x] A" not in ctx
        assert "B" in ctx
