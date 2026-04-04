"""PromptSpec framework — program-controlled prompt assembly.

Each action (plan, adjust, execute, etc.) has a PromptSpec that defines:
- What model to use
- What instruction to give
- What inputs the program provides (LLM only sees what we feed it)
- How to validate the output format
- No free-form prompt construction in handler code

Bot handlers become: look up spec → build inputs → build_prompt → run_claude → validate → act.
"""

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class PromptSpec:
    action: str
    model: str  # "opus" or "sonnet"
    instruction: str  # Template with {placeholders} for inputs
    input_keys: list[str]  # Required input names
    output_validator: Callable[[str], bool] | None = None
    include_previous: bool = True  # Whether to include prior step results in prompt

    def validate_output(self, output: str) -> bool:
        if self.output_validator is None:
            return True
        return self.output_validator(output)


def build_prompt(spec: PromptSpec, inputs: dict[str, str]) -> str:
    """Assemble prompt from spec + program-provided inputs.
    Raises KeyError if a required input is missing.
    """
    for key in spec.input_keys:
        if key not in inputs:
            raise KeyError(f"Missing required input: {key}")
    return spec.instruction.format(**inputs)


def _has_checklist(output: str) -> bool:
    """Validate that output contains at least one checklist item."""
    return "- [ ]" in output


# ── /plan specs ──

PLAN_SPECS: dict[str, PromptSpec] = {
    "plan_analyze": PromptSpec(
        action="PLAN",
        model="opus",
        instruction=(
            "你是計畫規劃助手。根據以下草稿產出具體的 implementation checklist。\n\n"
            "【待規劃的草稿】\n{draft}\n\n"
            "{planned_context}"
            "【輸出要求】\n"
            "- 格式：markdown checklist（- [ ] task description — branch: feature/xxx, repo: reponame）\n"
            "- 標註 Phase（可平行的放同一個 Phase），標註依賴關係\n"
            "- 考慮：架構影響、實作順序、風險\n"
            "- 只輸出 checklist 和 Phase 分組，不要分析、不要評論、不要檢查 repo 狀態"
        ),
        input_keys=["draft", "planned_context"],
        output_validator=_has_checklist,
    ),

    "plan_adjust": PromptSpec(
        action="ADJUST",
        model="opus",
        instruction=(
            "你是計畫調整助手。根據使用者的調整要求修改目前計畫。\n\n"
            "【目前計畫】\n{current_plan}\n\n"
            "【調整要求】\n{user_feedback}\n\n"
            "【輸出要求】\n"
            "- 只輸出完整的新版 checklist\n"
            "- 格式：markdown checklist（- [ ] task description — branch: feature/xxx, repo: reponame）\n"
            "- 不要分析現況、不要評論、不要檢查 repo 狀態\n"
            "- 不要解釋你改了什麼，直接給新版計畫"
        ),
        input_keys=["current_plan", "user_feedback"],
        output_validator=_has_checklist,
    ),

    "plan_execute": PromptSpec(
        action="EXECUTE",
        model="sonnet",
        instruction=(
            "請執行以下任務：\n\n{task}\n\n"
            "完成後簡述做了什麼。"
        ),
        input_keys=["task"],
        # Execute accepts any output — the task itself is the validation
    ),
}


# ── /morning specs ──

MORNING_SPECS: dict[str, PromptSpec] = {
    "gather_focus": PromptSpec(
        action="MORNING_FOCUS",
        model="sonnet",
        instruction=(
            "[系統] 今天是 {today}。\n"
            "讀 profile/current-focus.md，回傳目前三條主線的重點摘要（不超過 200 字）。"
        ),
        input_keys=["today"],
        include_previous=False,
    ),
    "gather_recent": PromptSpec(
        action="MORNING_RECENT",
        model="sonnet",
        instruction=(
            "讀最近 3 天的 daily/*.md，回傳近期進度摘要（不超過 200 字）。"
            "有哪些完成了、哪些卡住了？"
        ),
        input_keys=[],
        include_previous=False,
    ),
    "synthesize": PromptSpec(
        action="MORNING_SYNTHESIZE",
        model="opus",
        instruction=(
            "根據以上主線和近期進度，給 Dante 今日建議：\n"
            "1. 今天最重要的 1-2 件事（根據主線優先順序）\n"
            "2. 學習可以從哪裡繼續\n"
            "3. 有沒有什麼卡住的需要處理\n"
            "請簡潔，不超過 300 字。"
        ),
        input_keys=[],
        include_previous=True,
    ),
}
