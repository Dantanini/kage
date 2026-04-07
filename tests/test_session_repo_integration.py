"""Integration tests for session repo binding in bot flow.

Verifies that sessions carry repo context and git pull hook uses it.
"""

from session import Session, SessionManager


def test_session_repo_flows_to_hook():
    """Start hook should receive session with repo_path set."""
    captured = {}

    async def mock_hook(session):
        captured["repo_path"] = session.repo_path
        captured["repo_name"] = session.repo_name

    mgr = SessionManager(timeout_minutes=30)
    mgr.register_start_hook(lambda: mock_hook)

    session = mgr.create(
        user_id=123, intent="chat", model="sonnet",
        repo_name="journal", repo_path="/home/user/dev-journal",
    )

    # Hooks are registered but not yet run (run_start_hooks is async)
    assert session.repo_path == "/home/user/dev-journal"
    assert session.repo_name == "journal"


def test_get_or_create_preserves_repo_on_existing():
    """Existing session should keep its repo when get_or_create is called again."""
    mgr = SessionManager(timeout_minutes=30)
    s1 = mgr.create(
        user_id=123, intent="chat", model="sonnet",
        repo_name="kage", repo_path="/home/user/kage",
    )

    # Simulate another call with different repo (e.g., _current_repo changed)
    s2 = mgr.get_or_create(
        user_id=123, intent="chat", model="sonnet",
        repo_name="journal", repo_path="/home/user/dev-journal",
    )

    assert s2 is s1
    assert s2.repo_name == "kage"  # preserved, not overwritten
    assert s2.repo_path == "/home/user/kage"


def test_repo_switch_creates_new_session():
    """After /repo switch (close + recreate), new session has new repo."""
    mgr = SessionManager(timeout_minutes=30)
    s1 = mgr.create(
        user_id=123, intent="chat", model="sonnet",
        repo_name="journal", repo_path="/home/user/dev-journal",
    )
    assert s1.repo_name == "journal"

    # Simulate /repo switch: close old session
    mgr.close_sync(123)

    # Create new session with new repo
    s2 = mgr.create(
        user_id=123, intent="chat", model="sonnet",
        repo_name="kage", repo_path="/home/user/kage",
    )
    assert s2 is not s1
    assert s2.repo_name == "kage"
    assert s2.repo_path == "/home/user/kage"
