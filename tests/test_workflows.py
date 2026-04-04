"""Tests for workflows module."""

import pytest

from workflows import (
    WorkflowStep,
    WorkflowResult,
    build_morning_steps,
    build_evening_steps,
    run_workflow,
    format_workflow_results,
)


class TestWorkflowSteps:
    """Test step builders produce correct structure."""

    def test_morning_has_three_steps(self):
        steps = build_morning_steps("2026-04-01")
        assert len(steps) == 3

    def test_morning_last_step_is_opus(self):
        steps = build_morning_steps()
        assert steps[-1].model == "opus"

    def test_morning_first_steps_are_sonnet(self):
        steps = build_morning_steps()
        assert steps[0].model == "sonnet"
        assert steps[1].model == "sonnet"

    def test_morning_last_step_includes_previous(self):
        steps = build_morning_steps()
        assert steps[-1].include_previous is True
        assert steps[0].include_previous is False

    def test_evening_has_three_steps(self):
        steps = build_evening_steps("2026-04-01")
        assert len(steps) == 3

    def test_evening_includes_date(self):
        steps = build_evening_steps("2026-04-01")
        assert "2026-04-01" in steps[0].prompt

    def test_evening_includes_memory_and_readme_check(self):
        steps = build_evening_steps("2026-04-01")
        memory_step = steps[1]
        assert "memory" in memory_step.prompt.lower() or "記憶" in memory_step.prompt
        assert "README" in memory_step.prompt

    def test_evening_first_step_no_previous(self):
        steps = build_evening_steps("2026-04-01")
        assert steps[0].include_previous is False

    def test_evening_last_step_is_opus(self):
        steps = build_evening_steps("2026-04-01")
        assert steps[-1].model == "opus"

    def test_evening_last_step_includes_previous(self):
        steps = build_evening_steps("2026-04-01")
        assert steps[-1].include_previous is True


class TestRunWorkflow:
    """Test workflow execution chain."""

    @pytest.mark.asyncio
    async def test_all_steps_succeed(self):
        async def mock_claude(prompt, model, sid, resume, cwd):
            return f"result for {model}"

        steps = [
            WorkflowStep(name="a", prompt="do a", model="sonnet", include_previous=False),
            WorkflowStep(name="b", prompt="do b", model="opus", include_previous=True),
        ]
        results = await run_workflow(steps, mock_claude)
        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_stops_on_failure(self):
        call_count = 0

        async def mock_claude(prompt, model, sid, resume, cwd):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "⚠️ Claude 執行失敗"
            return "should not reach"

        steps = [
            WorkflowStep(name="a", prompt="do a", model="sonnet", include_previous=False),
            WorkflowStep(name="b", prompt="do b", model="opus", include_previous=True),
        ]
        results = await run_workflow(steps, mock_claude)
        assert len(results) == 1
        assert results[0].success is False
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_previous_context_injected(self):
        prompts_received = []

        async def mock_claude(prompt, model, sid, resume, cwd):
            prompts_received.append(prompt)
            return "step output"

        steps = [
            WorkflowStep(name="gather", prompt="gather data", model="sonnet", include_previous=False),
            WorkflowStep(name="analyze", prompt="analyze it", model="opus", include_previous=True),
        ]
        await run_workflow(steps, mock_claude)
        # Second prompt should contain first step's output
        assert "step output" in prompts_received[1]

    @pytest.mark.asyncio
    async def test_cwd_passed_through(self):
        cwds = []

        async def mock_claude(prompt, model, sid, resume, cwd):
            cwds.append(cwd)
            return "ok"

        steps = [WorkflowStep(name="a", prompt="x", model="sonnet")]
        await run_workflow(steps, mock_claude, cwd="/my/repo")
        assert cwds == ["/my/repo"]


class TestFormatResults:
    """Test result formatting."""

    def test_empty_results(self):
        out = format_workflow_results([])
        assert "⚠️" in out

    def test_success_shows_last_output(self):
        results = [
            WorkflowResult(step_name="a", output="intermediate", success=True),
            WorkflowResult(step_name="b", output="final answer", success=True),
        ]
        assert format_workflow_results(results) == "final answer"

    def test_failure_shows_all(self):
        results = [
            WorkflowResult(step_name="a", output="good", success=True),
            WorkflowResult(step_name="b", output="⚠️ boom", success=False),
        ]
        out = format_workflow_results(results)
        assert "good" in out
        assert "boom" in out
