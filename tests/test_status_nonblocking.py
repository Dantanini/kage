"""Tests for /status non-blocking behavior.

/status must respond immediately even when another handler is busy
(e.g. claude -p running for 15 minutes).

Two layers needed:
1. Application.concurrent_updates=True — process multiple updates at once
2. /status handler block=False — don't wait for handler to finish
"""

import pytest


class TestConcurrentUpdatesEnabled:
    """Application must allow concurrent update processing."""

    def test_app_has_concurrent_updates(self):
        """Application should be built with concurrent_updates=True."""
        import bot
        app = bot.Application.builder().token("fake:token").concurrent_updates(True).build()
        assert app.update_processor.max_concurrent_updates != 1


class TestStatusHandlerRegistration:
    """Verify /status is registered with block=False."""

    def test_status_handler_is_non_blocking(self):
        """The CommandHandler for /status must have block=False."""
        from telegram.ext import CommandHandler
        import bot

        app = bot.Application.builder().token("fake:token").build()
        bot._register_handlers(app)

        status_handlers = [
            h for group_handlers in app.handlers.values()
            for h in group_handlers
            if isinstance(h, CommandHandler) and "status" in h.commands
        ]
        assert len(status_handlers) == 1
        assert status_handlers[0].block is False


class TestBuildAppConcurrent:
    """Verify _build_app produces a concurrent-enabled app."""

    def test_build_app_returns_concurrent_app(self):
        """_build_app should set concurrent_updates=True."""
        import bot
        app = bot._build_app("fake:token")
        assert app.update_processor.max_concurrent_updates != 1
