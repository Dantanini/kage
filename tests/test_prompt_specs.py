"""Tests for prompt_specs — PromptSpec framework + /plan specs."""

import pytest
from prompt_specs import PromptSpec, PLAN_SPECS, MORNING_SPECS, EVENING_SPECS, COURSE_SPECS, build_prompt


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


class TestMorningSpecs:
    """Verify /morning specs exist, models, and input contracts."""

    def test_morning_has_three_specs(self):
        assert len(MORNING_SPECS) == 3

    def test_gather_focus_is_sonnet_no_previous(self):
        spec = MORNING_SPECS["gather_focus"]
        assert spec.model == "sonnet"
        assert spec.include_previous is False

    def test_gather_recent_is_sonnet_no_previous(self):
        spec = MORNING_SPECS["gather_recent"]
        assert spec.model == "sonnet"
        assert spec.include_previous is False

    def test_synthesize_is_opus_includes_previous(self):
        spec = MORNING_SPECS["synthesize"]
        assert spec.model == "opus"
        assert spec.include_previous is True

    def test_gather_focus_requires_today(self):
        spec = MORNING_SPECS["gather_focus"]
        assert "today" in spec.input_keys

    def test_gather_focus_injects_date(self):
        spec = MORNING_SPECS["gather_focus"]
        prompt = build_prompt(spec, {"today": "2026-04-04"})
        assert "2026-04-04" in prompt

    def test_gather_recent_no_required_inputs(self):
        spec = MORNING_SPECS["gather_recent"]
        assert spec.input_keys == []
        prompt = build_prompt(spec, {})
        assert "daily" in prompt

    def test_synthesize_no_required_inputs(self):
        spec = MORNING_SPECS["synthesize"]
        assert spec.input_keys == []
        prompt = build_prompt(spec, {})
        assert "300" in prompt  # word limit mentioned

    def test_all_morning_specs_have_instructions(self):
        for name, spec in MORNING_SPECS.items():
            assert spec.instruction, f"{name} has empty instruction"


class TestEveningSpecs:
    """Verify /evening specific specs exist and are correct."""

    def test_has_three_steps(self):
        assert len(EVENING_SPECS) == 3

    def test_gather_today_exists(self):
        spec = EVENING_SPECS["gather_today"]
        assert spec.model == "sonnet"
        assert "today" in spec.input_keys
        assert spec.include_previous is False

    def test_update_memory_and_readme_exists(self):
        spec = EVENING_SPECS["update_memory_and_readme"]
        assert spec.model == "sonnet"
        assert spec.include_previous is True

    def test_update_daily_and_commit_exists(self):
        spec = EVENING_SPECS["update_daily_and_commit"]
        assert spec.model == "opus"
        assert "today" in spec.input_keys
        assert spec.include_previous is True

    def test_gather_today_prompt_includes_date(self):
        spec = EVENING_SPECS["gather_today"]
        prompt = build_prompt(spec, {"today": "2026-04-04"})
        assert "2026-04-04" in prompt

    def test_update_daily_prompt_includes_date(self):
        spec = EVENING_SPECS["update_daily_and_commit"]
        prompt = build_prompt(spec, {"today": "2026-04-04"})
        assert "2026-04-04" in prompt

    def test_all_specs_have_instructions(self):
        for name, spec in EVENING_SPECS.items():
            assert spec.instruction, f"{name} has empty instruction"


class TestCourseSpecs:
    """Verify /course specs exist and are correct."""

    def test_course_flush_exists(self):
        spec = COURSE_SPECS["course_flush"]
        assert spec.model == "opus"
        assert "qa_log" in spec.input_keys

    def test_course_flush_accepts_any_output(self):
        spec = COURSE_SPECS["course_flush"]
        assert spec.validate_output("已更新 learning/notes.md") is True

    def test_course_flush_prompt_contains_qa_log(self):
        spec = COURSE_SPECS["course_flush"]
        prompt = build_prompt(spec, {"qa_log": "Q: foo\nA: bar"})
        assert "Q: foo\nA: bar" in prompt

    def test_course_flush_prompt_mentions_learning_dir(self):
        spec = COURSE_SPECS["course_flush"]
        assert "learning/" in spec.instruction

    def test_course_flush_missing_qa_log_raises(self):
        spec = COURSE_SPECS["course_flush"]
        with pytest.raises(KeyError):
            build_prompt(spec, {})
