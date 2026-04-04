"""Tests for prompt_specs — PromptSpec framework + /plan specs."""

import pytest
from prompt_specs import PromptSpec, PLAN_SPECS, build_prompt


class TestPromptSpec:
    """PromptSpec dataclass validation."""

    def test_spec_has_required_fields(self):
        spec = PromptSpec(
            action="TEST",
            model="sonnet",
            instruction="do {input}",
            input_keys=["input"],
        )
        assert spec.action == "TEST"
        assert spec.model == "sonnet"

    def test_spec_default_validator_accepts_anything(self):
        spec = PromptSpec(
            action="TEST",
            model="sonnet",
            instruction="do something",
            input_keys=[],
        )
        assert spec.validate_output("any text") is True

    def test_spec_custom_validator(self):
        spec = PromptSpec(
            action="TEST",
            model="sonnet",
            instruction="produce checklist",
            input_keys=[],
            output_validator=lambda r: "- [ ]" in r,
        )
        assert spec.validate_output("- [ ] task A") is True
        assert spec.validate_output("here is my analysis...") is False


class TestBuildPrompt:
    """build_prompt assembles prompt from spec + inputs."""

    def test_basic_substitution(self):
        spec = PromptSpec(
            action="TEST",
            model="sonnet",
            instruction="請處理以下內容：\n\n{input}",
            input_keys=["input"],
        )
        prompt = build_prompt(spec, {"input": "hello world"})
        assert "hello world" in prompt
        assert "請處理以下內容" in prompt

    def test_multiple_inputs(self):
        spec = PromptSpec(
            action="TEST",
            model="opus",
            instruction="新草稿：\n{draft}\n\n已規劃（不要動）：\n{planned}",
            input_keys=["draft", "planned"],
        )
        prompt = build_prompt(spec, {"draft": "new idea", "planned": "existing task"})
        assert "new idea" in prompt
        assert "existing task" in prompt

    def test_missing_input_raises(self):
        spec = PromptSpec(
            action="TEST",
            model="sonnet",
            instruction="{input}",
            input_keys=["input"],
        )
        with pytest.raises(KeyError):
            build_prompt(spec, {})

    def test_optional_input_with_default(self):
        spec = PromptSpec(
            action="TEST",
            model="sonnet",
            instruction="計畫：\n{planned}\n\n草稿：\n{draft}",
            input_keys=["planned", "draft"],
        )
        prompt = build_prompt(spec, {"planned": "", "draft": "something"})
        assert "something" in prompt


class TestPlanSpecs:
    """Verify /plan specific specs exist and are correct."""

    def test_plan_analyze_exists(self):
        spec = PLAN_SPECS["plan_analyze"]
        assert spec.model == "opus"
        assert "draft" in spec.input_keys

    def test_plan_adjust_exists(self):
        spec = PLAN_SPECS["plan_adjust"]
        assert spec.model == "opus"
        assert "user_feedback" in spec.input_keys
        assert "current_plan" in spec.input_keys

    def test_plan_execute_exists(self):
        spec = PLAN_SPECS["plan_execute"]
        assert spec.model == "sonnet"
        assert "task" in spec.input_keys

    def test_plan_analyze_requires_checklist_output(self):
        spec = PLAN_SPECS["plan_analyze"]
        assert spec.validate_output("- [ ] task A\n- [ ] task B") is True
        assert spec.validate_output("I analyzed the repo and found...") is False

    def test_plan_adjust_requires_checklist_output(self):
        spec = PLAN_SPECS["plan_adjust"]
        assert spec.validate_output("- [ ] updated task") is True
        assert spec.validate_output("看了一下 repo 狀態...") is False

    def test_plan_execute_accepts_any_output(self):
        spec = PLAN_SPECS["plan_execute"]
        assert spec.validate_output("done, created file X") is True

    def test_all_specs_have_instructions(self):
        for name, spec in PLAN_SPECS.items():
            assert spec.instruction, f"{name} has empty instruction"

    def test_plan_analyze_instruction_mentions_format(self):
        spec = PLAN_SPECS["plan_analyze"]
        assert "- [ ]" in spec.instruction or "checklist" in spec.instruction.lower()

    def test_plan_adjust_instruction_says_no_analysis(self):
        spec = PLAN_SPECS["plan_adjust"]
        assert "不要分析" in spec.instruction or "只輸出" in spec.instruction
