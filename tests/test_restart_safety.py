"""Tests for restart/release git safety — ensure failures are caught and reported.

Tests verify the helper function logic without importing bot.py (heavy deps).
"""


def _check_git_ready(checkout_result, pull_results):
    """Mirror of bot._check_git_ready for testing.

    Args:
        checkout_result: (returncode, stderr) from git checkout
        pull_results: list of (name, error_msg_or_none) from git pull

    Returns:
        (ok: bool, errors: list[str])
    """
    errors = []

    rc, stderr = checkout_result
    if rc != 0:
        errors.append(f"git checkout main failed: {stderr}")

    for name, err in pull_results:
        if err:
            errors.append(f"{name}: {err}")

    return (len(errors) == 0, errors)


class TestCheckGitReady:

    def test_all_success(self):
        ok, errors = _check_git_ready(
            (0, ""),
            [("kage", None), ("journal", None)],
        )
        assert ok is True
        assert errors == []

    def test_checkout_failure(self):
        ok, errors = _check_git_ready(
            (1, "error: Your local changes would be overwritten"),
            [("kage", None), ("journal", None)],
        )
        assert ok is False
        assert any("checkout" in e for e in errors)
        assert any("overwritten" in e for e in errors)

    def test_pull_failure_one_repo(self):
        ok, errors = _check_git_ready(
            (0, ""),
            [("kage", "CONFLICT (content): Merge conflict in bot.py"), ("journal", None)],
        )
        assert ok is False
        assert any("kage" in e for e in errors)
        assert any("CONFLICT" in e for e in errors)

    def test_pull_failure_both_repos(self):
        ok, errors = _check_git_ready(
            (0, ""),
            [("kage", "fatal: not a git repository"), ("journal", "Permission denied")],
        )
        assert ok is False
        assert len(errors) == 2

    def test_checkout_and_pull_both_fail(self):
        ok, errors = _check_git_ready(
            (128, "fatal: not a git repository"),
            [("kage", "Connection refused")],
        )
        assert ok is False
        assert len(errors) == 2

    def test_dirty_working_tree(self):
        ok, errors = _check_git_ready(
            (1, "error: Your local changes to the following files would be overwritten by checkout:\n\tbot.py"),
            [],
        )
        assert ok is False
        assert any("bot.py" in e for e in errors)
