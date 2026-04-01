"""Tests for notify module — shared Telegram notification utilities."""

from unittest.mock import patch, MagicMock

import pytest

from tg_notify import build_memory_save_message, send_telegram_message


class TestBuildMemorySaveMessage:
    """Build notification message for memory auto-save events."""

    def test_success_message_contains_indicator(self):
        msg = build_memory_save_message(success=True, qa_count=3)
        assert "✓" in msg or "success" in msg.lower() or "完成" in msg

    def test_success_message_contains_qa_count(self):
        msg = build_memory_save_message(success=True, qa_count=5)
        assert "5" in msg

    def test_failure_message_contains_error(self):
        msg = build_memory_save_message(success=False, error="Claude timeout")
        assert "Claude timeout" in msg

    def test_failure_message_has_fail_indicator(self):
        msg = build_memory_save_message(success=False, error="timeout")
        assert "✗" in msg or "fail" in msg.lower() or "失敗" in msg

    def test_zero_qa_count(self):
        msg = build_memory_save_message(success=True, qa_count=0)
        # Should still produce a valid message
        assert isinstance(msg, str) and len(msg) > 0


class TestSendTelegramMessage:
    """send_telegram_message sends via Telegram Bot API."""

    @patch("tg_notify.urllib.request.urlopen")
    def test_sends_request(self, mock_urlopen):
        mock_urlopen.return_value = MagicMock()
        send_telegram_message("test message", token="fake-token", chat_id="123")
        mock_urlopen.assert_called_once()

    @patch("tg_notify.urllib.request.urlopen")
    def test_request_contains_message(self, mock_urlopen):
        mock_urlopen.return_value = MagicMock()
        send_telegram_message("hello world", token="fake-token", chat_id="123")
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        assert b"hello world" in request.data

    @patch("tg_notify.urllib.request.urlopen", side_effect=Exception("network error"))
    def test_network_error_does_not_raise(self, mock_urlopen):
        """Notification failure should not crash the bot."""
        # Should not raise
        send_telegram_message("test", token="fake-token", chat_id="123")

    def test_missing_token_skips(self):
        """No token = no request, no crash."""
        # Should not raise
        send_telegram_message("test", token="", chat_id="123")
