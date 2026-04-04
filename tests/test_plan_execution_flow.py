"""Tests for plan execution flow — stop-and-wait + branch recording."""

import pytest
from pathlib import Path
from plan_v2 import PlanStore, PlanStatus


@pytest.fixture
def plan_store(tmp_path):
    return PlanStore(local_dir=str(tmp_path / ".local"))


class TestBranchRecording:
    """complete_item should record branch name in completed.md."""

    def test_complete_with_branch(self, plan_store):
        plan_store.append("task")
        plan_store.set_planned("- [ ] fix bug — branch: fix/bug, repo: kage")
        plan_store.set_executing()
        plan_store.complete_item("fix bug", branch="fix/bug")
        completed = plan_store.read_completed()
        assert "fix/bug" in completed
        assert "- [x]" in completed

    def test_complete_without_branch_still_works(self, plan_store):
        plan_store.append("task")
        plan_store.set_planned("- [ ] simple task")
        plan_store.set_executing()
        plan_store.complete_item("simple task")
        completed = plan_store.read_completed()
        assert "- [x]" in completed

    def test_get_branch_from_completed(self, plan_store):
        plan_store.append("task")
        plan_store.set_planned("- [ ] task A — branch: feat/a, repo: kage\n- [ ] task B — branch: feat/b, repo: kage")
        plan_store.set_executing()
        plan_store.complete_item("task A", branch="feat/a")
        plan_store.complete_item("task B", branch="feat/b")
        branches = plan_store.completed_branches()
        assert "feat/a" in branches
        assert "feat/b" in branches


class TestParsePlannedItem:
    """Parse branch and repo from planned.md items."""

    def test_parse_item_with_branch_and_repo(self, plan_store):
        plan_store.append("task")
        plan_store.set_planned("- [ ] fix bug — branch: fix/bug, repo: kage")
        items = plan_store.parse_planned_items()
        assert len(items) == 1
        assert items[0]["task"] == "fix bug"
        assert items[0]["branch"] == "fix/bug"
        assert items[0]["repo"] == "kage"

    def test_parse_item_without_metadata(self, plan_store):
        plan_store.append("task")
        plan_store.set_planned("- [ ] do something simple")
        items = plan_store.parse_planned_items()
        assert len(items) == 1
        assert items[0]["task"] == "do something simple"
        assert items[0]["branch"] is None
        assert items[0]["repo"] is None

    def test_parse_multiple_items(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned(
            "- [ ] task A — branch: feat/a, repo: kage\n"
            "- [ ] task B — branch: feat/b, repo: journal\n"
            "- [ ] task C"
        )
        items = plan_store.parse_planned_items()
        assert len(items) == 3
        assert items[0]["branch"] == "feat/a"
        assert items[1]["repo"] == "journal"
        assert items[2]["branch"] is None

    def test_parse_skips_completed_items(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] pending\n- [x] done")
        items = plan_store.parse_planned_items()
        assert len(items) == 1
        assert "pending" in items[0]["task"]


class TestExecutionState:
    """Track which item is currently being executed."""

    def test_current_item_index(self, plan_store):
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B\n- [ ] C")
        plan_store.set_executing()
        assert plan_store.current_item_index() == 0
        plan_store.complete_item("A")
        assert plan_store.current_item_index() == 0  # next pending is now first

    def test_no_current_item_when_all_done(self, plan_store):
        plan_store.append("task")
        plan_store.set_planned("- [ ] A")
        plan_store.set_executing()
        plan_store.complete_item("A")
        assert plan_store.current_item_index() is None
