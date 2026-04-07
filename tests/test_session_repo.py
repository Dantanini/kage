"""Tests for Session repo binding — Phase 1 of kage v2.

Sessions should carry their own repo context instead of relying on
the global _current_repo dict.
"""

import time
from session import Session, SessionManager


def test_session_has_repo_fields():
    """Session should have repo_name and repo_path fields."""
    s = Session(
        session_id="test-1",
        user_id=123,
        intent="chat",
        model="sonnet",
        repo_name="journal",
        repo_path="/home/user/dev-journal",
    )
    assert s.repo_name == "journal"
    assert s.repo_path == "/home/user/dev-journal"


def test_session_default_repo():
    """Session without explicit repo should default to None."""
    s = Session(
        session_id="test-2",
        user_id=123,
        intent="chat",
        model="sonnet",
    )
    assert s.repo_name is None
    assert s.repo_path is None


def test_session_manager_create_with_repo():
    """SessionManager.create should accept and set repo fields."""
    mgr = SessionManager(timeout_minutes=30)
    s = mgr.create(
        user_id=123,
        intent="chat",
        model="sonnet",
        repo_name="kage",
        repo_path="/home/user/kage",
    )
    assert s.repo_name == "kage"
    assert s.repo_path == "/home/user/kage"


def test_session_manager_get_or_create_with_repo():
    """get_or_create should pass repo fields to new sessions."""
    mgr = SessionManager(timeout_minutes=30)
    s = mgr.get_or_create(
        user_id=456,
        intent="chat",
        model="sonnet",
        repo_name="journal",
        repo_path="/home/user/dev-journal",
    )
    assert s.repo_name == "journal"
    assert s.repo_path == "/home/user/dev-journal"


def test_session_manager_get_or_create_preserves_existing():
    """get_or_create should NOT overwrite repo on existing session."""
    mgr = SessionManager(timeout_minutes=30)
    s1 = mgr.create(
        user_id=789,
        intent="chat",
        model="sonnet",
        repo_name="kage",
        repo_path="/home/user/kage",
    )
    s2 = mgr.get_or_create(
        user_id=789,
        intent="chat",
        model="sonnet",
        repo_name="journal",
        repo_path="/home/user/dev-journal",
    )
    # Should return the same session, repo unchanged
    assert s2 is s1
    assert s2.repo_name == "kage"


def test_session_switch_repo():
    """Session should support switching repo mid-conversation."""
    s = Session(
        session_id="test-3",
        user_id=123,
        intent="chat",
        model="sonnet",
        repo_name="journal",
        repo_path="/home/user/dev-journal",
    )
    s.repo_name = "kage"
    s.repo_path = "/home/user/kage"
    assert s.repo_name == "kage"
    assert s.repo_path == "/home/user/kage"
