"""Tests for session module — hooks, lifecycle, and management."""

import asyncio
import time

import pytest

from session import Session, SessionManager


class TestSessionHooks:
    """Test session lifecycle hook system."""

    @pytest.fixture
    def session(self):
        return Session(
            session_id="test-id",
            user_id=123,
            intent="chat",
            model="sonnet",
        )

    @pytest.mark.asyncio
    async def test_start_hooks_run_once(self, session):
        call_count = 0

        async def hook(s):
            nonlocal call_count
            call_count += 1

        session.add_start_hook(hook)
        await session.run_start_hooks()
        await session.run_start_hooks()  # second call should be no-op
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_end_hooks_run_every_time(self, session):
        call_count = 0

        async def hook(s):
            nonlocal call_count
            call_count += 1

        session.add_end_hook(hook)
        await session.run_end_hooks()
        await session.run_end_hooks()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_hook_receives_session(self, session):
        received = []

        async def hook(s):
            received.append(s)

        session.add_start_hook(hook)
        await session.run_start_hooks()
        assert received[0] is session

    @pytest.mark.asyncio
    async def test_failing_hook_does_not_block_others(self, session):
        results = []

        async def bad_hook(s):
            raise RuntimeError("boom")

        async def good_hook(s):
            results.append("ok")

        session.add_start_hook(bad_hook)
        session.add_start_hook(good_hook)
        errors = await session.run_start_hooks()
        assert len(errors) == 1
        assert "boom" in errors[0]
        assert results == ["ok"]

    @pytest.mark.asyncio
    async def test_multiple_hooks_run_in_order(self, session):
        order = []

        async def hook_a(s):
            order.append("a")

        async def hook_b(s):
            order.append("b")

        session.add_start_hook(hook_a)
        session.add_start_hook(hook_b)
        await session.run_start_hooks()
        assert order == ["a", "b"]


class TestSessionManagerHooks:
    """Test that SessionManager wires hooks to new sessions."""

    @pytest.mark.asyncio
    async def test_registered_hooks_attach_to_new_sessions(self):
        mgr = SessionManager(timeout_minutes=30)
        started = []

        mgr.register_start_hook(lambda: _make_hook(started, "start"))

        session = mgr.create(user_id=1, intent="chat", model="sonnet")
        await session.run_start_hooks()
        assert started == ["start"]

    @pytest.mark.asyncio
    async def test_close_runs_end_hooks(self):
        mgr = SessionManager(timeout_minutes=30)
        ended = []

        mgr.register_end_hook(lambda: _make_hook(ended, "end"))

        mgr.create(user_id=1, intent="chat", model="sonnet")
        await mgr.close(user_id=1)
        assert ended == ["end"]

    def test_close_sync_skips_hooks(self):
        mgr = SessionManager(timeout_minutes=30)
        ended = []

        mgr.register_end_hook(lambda: _make_hook(ended, "end"))

        mgr.create(user_id=1, intent="chat", model="sonnet")
        mgr.close_sync(user_id=1)
        assert ended == []  # hooks not called


class TestSessionExpiry:
    """Existing expiry tests still pass."""

    def test_session_expires(self):
        s = Session(
            session_id="x", user_id=1, intent="chat", model="sonnet",
            last_active=time.time() - 3600,
        )
        assert s.is_expired(1800) is True

    def test_session_not_expired(self):
        s = Session(
            session_id="x", user_id=1, intent="chat", model="sonnet",
        )
        assert s.is_expired(1800) is False

    def test_qa_log_size(self):
        s = Session(session_id="x", user_id=1, intent="chat", model="sonnet")
        s.qa_log = [("hello", "world"), ("foo", "bar")]
        assert s.qa_log_size() == len("hello") + len("world") + len("foo") + len("bar")


def _make_hook(collector: list, label: str):
    async def hook(session):
        collector.append(label)
    return hook
