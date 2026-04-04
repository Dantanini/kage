"""Tests for /plan bot integration — button flow + plan_v2 + executor."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from plan_v2 import PlanStore, PlanStatus


@pytest.fixture
def plan_store(tmp_path):
    return PlanStore(local_dir=str(tmp_path / ".local"))


class TestPlanButtonFlow:
    """Simulate the TG button flow for /plan."""

    def test_plan_empty_shows_three_buttons(self, plan_store):
        """When no plan exists, show status + 3 buttons."""
        status = plan_store.status
        assert status == PlanStatus.EMPTY
        # Bot should show: 📝撰寫 🧠規劃 🔨執行
        # 規劃 and 執行 should be disabled/hidden when empty

    def test_plan_with_draft_shows_content_and_buttons(self, plan_store):
        plan_store.append("改 README")
        plan_store.append("改 CLAUDE.md")
        assert plan_store.status == PlanStatus.DRAFT
        content = plan_store.read()
        assert "改 README" in content
        assert "改 CLAUDE.md" in content

    def test_write_button_appends_without_llm(self, plan_store):
        """撰寫 = pure append, no LLM."""
        plan_store.append("task 1")
        plan_store.append("task 2")
        # No LLM was called — just file append
        content = plan_store.read()
        assert "task 1" in content
        assert "task 2" in content
        assert plan_store.status == PlanStatus.DRAFT

    def test_plan_button_sets_planned_status(self, plan_store):
        """規劃 button → Opus produces checklist → status becomes PLANNED."""
        plan_store.append("改 README")
        # Simulate Opus output
        opus_output = "## Phase 1\n- [ ] 改 README — branch: docs/readme"
        plan_store.set_planned(opus_output)
        assert plan_store.status == PlanStatus.PLANNED
        assert "Phase 1" in plan_store.read()

    def test_adjust_button_keeps_planned_status(self, plan_store):
        """調整 = user feedback → re-plan → still PLANNED."""
        plan_store.append("task")
        plan_store.set_planned("- [ ] original plan")
        # User says "add error handling"
        # Opus re-plans
        plan_store.set_planned("- [ ] original plan\n- [ ] add error handling")
        assert plan_store.status == PlanStatus.PLANNED
        assert "error handling" in plan_store.read()

    def test_execute_button_sets_executing(self, plan_store):
        """執行 button → status becomes EXECUTING."""
        plan_store.append("task")
        plan_store.set_planned("- [ ] do it")
        plan_store.set_executing()
        assert plan_store.status == PlanStatus.EXECUTING

    def test_pause_during_execution(self, plan_store):
        """暫停 → back to PLANNED, pending items preserved."""
        plan_store.append("tasks")
        plan_store.set_planned("- [ ] A\n- [ ] B")
        plan_store.set_executing()
        plan_store.complete_item("A")
        plan_store.pause()
        assert plan_store.status == PlanStatus.PLANNED
        assert plan_store.pending_items() == ["- [ ] B"]

    def test_full_lifecycle(self, plan_store):
        """Complete flow: draft → planned → executing → done."""
        # 1. 撰寫
        plan_store.append("改 README")
        plan_store.append("改 CLAUDE.md")
        assert plan_store.status == PlanStatus.DRAFT

        # 2. 規劃 (Opus)
        plan_store.set_planned(
            "## Phase 1\n"
            "- [ ] 改 README — branch: docs/readme, repo: journal\n"
            "- [ ] 改 CLAUDE.md — branch: docs/claude-md, repo: journal"
        )
        assert plan_store.status == PlanStatus.PLANNED

        # 3. 執行
        plan_store.set_executing()
        assert plan_store.status == PlanStatus.EXECUTING

        # 4. 逐項完成
        plan_store.complete_item("改 README")
        assert not plan_store.all_completed()
        plan_store.complete_item("改 CLAUDE.md")
        assert plan_store.all_completed()

        # 5. 歸檔
        archived = plan_store.archive_completed()
        assert "README" in archived
        assert plan_store.status == PlanStatus.EMPTY


class TestPlanDisplay:
    """What the bot should show for each status."""

    def test_empty_display(self, plan_store):
        """Empty → show '📭 目前無計畫' + only 撰寫 enabled."""
        assert plan_store.status == PlanStatus.EMPTY
        assert not plan_store.has_plan()

    def test_draft_display(self, plan_store):
        """Draft → show content + 撰寫/規劃 enabled, 執行 disabled."""
        plan_store.append("some idea")
        assert plan_store.status == PlanStatus.DRAFT
        assert plan_store.has_plan()

    def test_planned_display(self, plan_store):
        """Planned → show checklist + 調整/執行 enabled."""
        plan_store.append("task")
        plan_store.set_planned("- [ ] step 1\n- [ ] step 2")
        assert plan_store.status == PlanStatus.PLANNED
        pending = plan_store.pending_items()
        assert len(pending) == 2

    def test_executing_display(self, plan_store):
        """Executing → show progress + 暫停 enabled."""
        plan_store.append("task")
        plan_store.set_planned("- [ ] A\n- [ ] B")
        plan_store.set_executing()
        plan_store.complete_item("A")
        pending = plan_store.pending_items()
        assert len(pending) == 1


class TestModelSwitching:
    """Verify correct model assignment per phase."""

    def test_draft_phase_no_model(self, plan_store):
        """撰寫 phase uses no LLM."""
        plan_store.append("test")
        # No model needed — pure file operation
        assert plan_store.status == PlanStatus.DRAFT

    def test_plan_phase_needs_opus(self, plan_store):
        """規劃 phase should use opus."""
        plan_store.append("task")
        # Caller (bot.py) should use model="opus" for planning
        # We just verify the store transitions correctly
        plan_store.set_planned("- [ ] plan")
        assert plan_store.status == PlanStatus.PLANNED

    def test_execute_phase_needs_sonnet(self, plan_store):
        """執行 phase should use sonnet."""
        plan_store.append("task")
        plan_store.set_planned("- [ ] plan")
        plan_store.set_executing()
        assert plan_store.status == PlanStatus.EXECUTING
        # Caller (bot.py) should use model="sonnet" for execution
