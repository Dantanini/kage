"""Tests for auto_deploy — decision logic for automated deployment."""

import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from auto_deploy import has_new_commits, is_bot_idle, build_notify_message, should_retry, RETRY_HOURS


class TestHasNewCommits:
    """Detect when origin/main has commits not in local main."""

    def test_no_new_commits(self):
        with patch("auto_deploy.run_git") as mock:
            # Same hash = no new commits
            mock.return_value = ""
            assert has_new_commits() is False

    def test_has_new_commits(self):
        with patch("auto_deploy.run_git") as mock:
            mock.return_value = "abc1234 feat: new feature"
            assert has_new_commits() is True

    def test_fetch_failure_returns_false(self):
        with patch("auto_deploy.run_git", side_effect=RuntimeError("network")):
            assert has_new_commits() is False


class TestIsBotIdle:
    """Check if bot has no active sessions (based on timestamp file)."""

    def test_no_timestamp_file_is_idle(self, tmp_path):
        """No file = bot hasn't been used = idle."""
        assert is_bot_idle(tmp_path / "last_activity", idle_minutes=30) is True

    def test_old_timestamp_is_idle(self, tmp_path):
        ts_file = tmp_path / "last_activity"
        # Write a timestamp from 60 minutes ago
        ts_file.write_text(str(time.time() - 3600))
        assert is_bot_idle(ts_file, idle_minutes=30) is True

    def test_recent_timestamp_is_not_idle(self, tmp_path):
        ts_file = tmp_path / "last_activity"
        # Write current timestamp
        ts_file.write_text(str(time.time()))
        assert is_bot_idle(ts_file, idle_minutes=30) is False

    def test_corrupt_timestamp_is_idle(self, tmp_path):
        """Corrupt file should be treated as idle (safe to deploy)."""
        ts_file = tmp_path / "last_activity"
        ts_file.write_text("not-a-number")
        assert is_bot_idle(ts_file, idle_minutes=30) is True


class TestBuildNotifyMessage:
    """Build Telegram notification message for deploy result."""

    def test_success_message(self):
        msg = build_notify_message(success=True, commits_summary="2 feat, 1 fix")
        assert "success" in msg.lower() or "完成" in msg or "✓" in msg
        assert "2 feat" in msg

    def test_failure_message(self):
        msg = build_notify_message(success=False, error="git pull failed")
        assert "fail" in msg.lower() or "失敗" in msg or "✗" in msg
        assert "git pull" in msg

    def test_skipped_message(self):
        msg = build_notify_message(success=None, reason="bot is active")
        assert "skip" in msg.lower() or "跳過" in msg
        assert "active" in msg


class TestShouldRetry:
    """Decide whether to retry deployment after being skipped due to active bot."""

    def test_first_attempt_can_retry(self):
        """Hour 0 (03:00) — first skip, should retry later."""
        assert should_retry(attempt=0) is True

    def test_max_attempts_reached(self):
        """After RETRY_HOURS attempts, give up."""
        assert should_retry(attempt=RETRY_HOURS) is False

    def test_mid_attempts_can_retry(self):
        assert should_retry(attempt=1) is True

    def test_retry_hours_is_three(self):
        """Retry window is 03:00–06:00 (3 retries max)."""
        assert RETRY_HOURS == 3
