"""Tests for plan error handling improvements."""

from prompt_specs import _has_checklist


def test_has_checklist_valid():
    assert _has_checklist("- [ ] Task one\n- [ ] Task two")


def test_has_checklist_with_phases():
    assert _has_checklist("## Phase 1\n\n- [ ] Task one\n\n## Phase 2\n\n- [ ] Task two")


def test_has_checklist_invalid():
    assert not _has_checklist("This is just text without checklist")


def test_has_checklist_empty():
    assert not _has_checklist("")


def test_has_checklist_wrong_format():
    """Markdown list without checkbox should fail."""
    assert not _has_checklist("- Task one\n- Task two")
