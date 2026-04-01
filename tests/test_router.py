"""Tests for router module."""

import pytest

from router import COMMAND_ROUTES, DEFAULT_MODEL, route


class TestNoDuplicateKeys:
    """Ensure COMMAND_ROUTES has no duplicate keys (Python dicts silently overwrite)."""

    def test_no_duplicate_keys_in_source(self):
        """Parse router.py source to catch duplicate dict keys that Python silently overwrites."""
        from pathlib import Path
        import re

        source = (Path(__file__).parent.parent / "router.py").read_text(encoding="utf-8")
        keys = re.findall(r'^\s+"(/\w+)":', source, re.MULTILINE)
        duplicates = [k for k in keys if keys.count(k) > 1]
        assert duplicates == [], f"Duplicate keys in COMMAND_ROUTES: {set(duplicates)}"


class TestCommandRouting:
    """Test that commands route to the correct model and intent."""

    @pytest.mark.parametrize(
        "message, expected_model, expected_intent",
        [
            ("/morning", "opus", "morning"),
            ("/evening", "opus", "evening"),
            ("/course", "opus", "course"),
            ("/opus", "opus", "chat"),
            ("/sonnet", "sonnet", "chat"),
            ("/note", "sonnet", "note"),
            ("/done", "sonnet", "done"),
            ("/restart", "sonnet", "restart"),
            ("/release", "sonnet", "release"),
        ],
    )
    def test_command_routes(self, message, expected_model, expected_intent):
        model, intent = route(message)
        assert model == expected_model
        assert intent == expected_intent

    def test_command_with_trailing_text(self):
        model, intent = route("/opus 請幫我看這段 code")
        assert model == "opus"
        assert intent == "chat"

    def test_command_with_leading_whitespace(self):
        model, intent = route("  /morning")
        assert model == "opus"
        assert intent == "morning"


class TestDefaultRouting:
    """Test fallback behavior for non-command messages."""

    def test_plain_text_uses_default(self):
        model, intent = route("你好")
        assert model == DEFAULT_MODEL
        assert intent == "chat"

    def test_custom_default_model(self):
        model, intent = route("你好", model_map={"default": "opus"})
        assert model == "opus"
        assert intent == "chat"

    def test_empty_message(self):
        model, intent = route("")
        assert model == DEFAULT_MODEL
        assert intent == "chat"

    def test_unknown_command(self):
        model, intent = route("/unknown")
        assert model == DEFAULT_MODEL
        assert intent == "chat"
