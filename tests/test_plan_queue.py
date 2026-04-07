"""Tests for plan execution queue — select items and order via buttons."""

import importlib.util
import sys
from pathlib import Path

# Load bot.py's PlanExecutionQueue without importing the full module
# (bot.py has heavy deps like yaml, telegram). Extract the class source.
_bot_path = Path(__file__).resolve().parent.parent / "bot.py"
_bot_source = _bot_path.read_text(encoding="utf-8")

# Find and exec just the PlanExecutionQueue class
_start = _bot_source.index("class PlanExecutionQueue:")
_end = _bot_source.index("\n\n\n", _start)  # class ends at double blank line
exec(_bot_source[_start:_end])


class TestPlanQueue:
    """In-memory queue for tracking user-selected execution order."""

    def test_empty_queue(self):
        q = PlanExecutionQueue()  # noqa: F821
        assert q.items() == []
        assert q.size() == 0

    def test_add_item(self):
        q = PlanExecutionQueue()  # noqa: F821
        q.add(0, "Fix footer link")
        assert q.size() == 1
        assert q.items()[0] == {"index": 0, "task": "Fix footer link"}

    def test_add_preserves_order(self):
        q = PlanExecutionQueue()  # noqa: F821
        q.add(2, "Task C")
        q.add(0, "Task A")
        q.add(1, "Task B")
        indices = [item["index"] for item in q.items()]
        assert indices == [2, 0, 1]  # insertion order, not sorted

    def test_add_duplicate_ignored(self):
        q = PlanExecutionQueue()  # noqa: F821
        q.add(0, "Task A")
        result = q.add(0, "Task A")
        assert result is False
        assert q.size() == 1

    def test_is_selected(self):
        q = PlanExecutionQueue()  # noqa: F821
        q.add(0, "Task A")
        assert q.is_selected(0)
        assert not q.is_selected(1)

    def test_clear(self):
        q = PlanExecutionQueue()  # noqa: F821
        q.add(0, "Task A")
        q.add(1, "Task B")
        q.clear()
        assert q.size() == 0

    def test_position(self):
        q = PlanExecutionQueue()  # noqa: F821
        q.add(2, "Task C")
        q.add(0, "Task A")
        assert q.position(2) == 1  # first added = position 1
        assert q.position(0) == 2  # second added = position 2
        assert q.position(5) is None  # not in queue
