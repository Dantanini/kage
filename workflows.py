"""Workflow chains — multi-step code-defined workflows.

Replaces monolithic prompt templates with step-by-step execution.
Each step uses the right model and feeds results to the next step.
Inspired by Claude Code's query.ts step-by-step tool execution loop.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date

from prompt_specs import MORNING_SPECS, EVENING_SPECS, build_prompt

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStep:
    """A single step in a workflow chain."""
    name: str
    prompt: str
    model: str = "sonnet"
    include_previous: bool = True  # Include previous step results in prompt


@dataclass
class WorkflowResult:
    """Result of a single workflow step."""
    step_name: str
    output: str
    success: bool

    @property
    def failed(self) -> bool:
        return not self.success


def build_morning_steps(today: str | None = None) -> list[WorkflowStep]:
    """Build the morning workflow steps from MORNING_SPECS."""
    today = today or date.today().isoformat()
    inputs_by_step: dict[str, dict[str, str]] = {
        "gather_focus": {"today": today},
        "gather_recent": {},
        "synthesize": {},
    }
    return [
        WorkflowStep(
            name=name,
            prompt=build_prompt(spec, inputs_by_step[name]),
            model=spec.model,
            include_previous=spec.include_previous,
        )
        for name, spec in MORNING_SPECS.items()
    ]


def build_evening_steps(today: str | None = None, completed_items: str = "") -> list[WorkflowStep]:
    """Build the evening workflow steps from EVENING_SPECS.

    Args:
        today: Date string in YYYY-MM-DD format. Defaults to today.
        completed_items: Content from plan_store.read_completed(). If non-empty,
            included in the daily update step so completed tasks are recorded.
    """
    today = today or date.today().isoformat()
    inputs_by_step: dict[str, dict[str, str]] = {
        "gather_today": {"today": today},
        "update_memory_and_readme": {},
        "update_daily_and_commit": {"today": today},
    }

    plan_section = ""
    if completed_items:
        plan_section = (
            f"\n\n【今日已完成的計畫項目】\n{completed_items}\n"
            f"請把這些完成項目也寫進 daily/{today}.md。"
        )

    steps = [
        WorkflowStep(
            name=name,
            prompt=build_prompt(spec, inputs_by_step[name]),
            model=spec.model,
            include_previous=spec.include_previous,
        )
        for name, spec in EVENING_SPECS.items()
    ]

    # Inject completed plan items into the commit step
    if plan_section:
        steps[-1] = WorkflowStep(
            name=steps[-1].name,
            prompt=steps[-1].prompt + plan_section,
            model=steps[-1].model,
            include_previous=steps[-1].include_previous,
        )

    return steps


async def run_workflow(
    steps: list[WorkflowStep],
    run_claude_fn,
    cwd: str | None = None,
) -> list[WorkflowResult]:
    """Execute a workflow chain step by step.

    Args:
        steps: Ordered list of workflow steps.
        run_claude_fn: async callable(prompt, model, session_id, resume, cwd) -> str
        cwd: Working directory for Claude.

    Returns:
        List of WorkflowResult for each step.
    """
    results: list[WorkflowResult] = []
    accumulated_context = []

    for step in steps:
        # Build prompt with optional previous context
        if step.include_previous and accumulated_context:
            context = "\n\n".join(
                f"[{r.step_name} 結果]\n{r.output}" for r in results if r.success
            )
            full_prompt = f"{context}\n\n{step.prompt}"
        else:
            full_prompt = step.prompt

        session_id = str(uuid.uuid4())
        output = await run_claude_fn(
            full_prompt, step.model, session_id, False, cwd,
        )

        success = not output.startswith("⚠️")
        result = WorkflowResult(
            step_name=step.name,
            output=output,
            success=success,
        )
        results.append(result)

        if success:
            accumulated_context.append(output)

        if not success:
            logger.warning(f"Workflow step '{step.name}' failed: {output[:200]}")
            break  # Stop chain on failure

    return results


def format_workflow_results(results: list[WorkflowResult]) -> str:
    """Format workflow results for display to user."""
    if not results:
        return "⚠️ Workflow 沒有產生任何結果"

    # If last step succeeded, show its output (it's the synthesis)
    last = results[-1]
    if last.success:
        return last.output

    # On failure, show what we got + error
    parts = []
    for r in results:
        if r.success:
            parts.append(r.output)
        else:
            parts.append(f"⚠️ 步驟 {r.step_name} 失敗：{r.output[:300]}")
    return "\n\n---\n\n".join(parts)
