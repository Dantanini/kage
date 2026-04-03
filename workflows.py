"""Workflow chains — multi-step code-defined workflows.

Replaces monolithic prompt templates with step-by-step execution.
Each step uses the right model and feeds results to the next step.
Inspired by Claude Code's query.ts step-by-step tool execution loop.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date

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
    """Build the morning workflow steps."""
    today = today or date.today().isoformat()
    return [
        WorkflowStep(
            name="gather_focus",
            prompt=f"[系統] 今天是 {today}。\n讀 profile/current-focus.md，回傳目前三條主線的重點摘要（不超過 200 字）。",
            model="sonnet",
            include_previous=False,
        ),
        WorkflowStep(
            name="gather_recent",
            prompt="讀最近 3 天的 daily/*.md，回傳近期進度摘要（不超過 200 字）。有哪些完成了、哪些卡住了？",
            model="sonnet",
            include_previous=False,
        ),
        WorkflowStep(
            name="synthesize",
            prompt=(
                "根據以上主線和近期進度，給 Dante 今日建議：\n"
                "1. 今天最重要的 1-2 件事（根據主線優先順序）\n"
                "2. 學習可以從哪裡繼續\n"
                "3. 有沒有什麼卡住的需要處理\n"
                "請簡潔，不超過 300 字。"
            ),
            model="opus",
            include_previous=True,
        ),
    ]


def build_evening_steps(today: str | None = None) -> list[WorkflowStep]:
    """Build the evening workflow steps."""
    today = today or date.today().isoformat()
    return [
        WorkflowStep(
            name="gather_today",
            prompt=(
                f"[系統] 今天是 {today}。\n"
                f"讀今天的 daily/{today}.md（如果存在）和 inbox/raw-notes.md，"
                f"回傳今天做了什麼的摘要（不超過 200 字）。"
            ),
            model="sonnet",
            include_previous=False,
        ),
        WorkflowStep(
            name="update_memory_and_readme",
            prompt=(
                f"根據以上摘要和今天的對話，執行以下檢查和更新：\n"
                f"1. 更新 memory/kage-memory/ 底下的檔案（如果有新的 lessons、task 進度變化）\n"
                f"2. 檢查對使用者有沒有新的觀察或評估值得記錄\n"
                f"3. 檢查 ~/kage/README.md 是否跟現有功能一致（指令表、test 數量、架構描述）\n"
                f"4. 檢查 dev-journal 的 README.md 是否需要更新\n"
                f"只回報需要更新的項目和你做了什麼改動（不超過 200 字），沒有需要更新的就說「記憶和 README 皆為最新」。"
            ),
            model="sonnet",
            include_previous=True,
        ),
        WorkflowStep(
            name="update_daily_and_commit",
            prompt=(
                f"根據以上所有資訊：\n"
                f"1. 更新或建立 daily/{today}.md\n"
                f"2. 更新 learning/INDEX.md（如果有變動）\n"
                f"3. 執行 python3 scripts/validate.py\n"
                f"4. 執行 python3 scripts/commit.py \"日結: {today}\"\n"
                f"5. 回報今天的摘要（不超過 200 字）"
            ),
            model="opus",
            include_previous=True,
        ),
    ]


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
