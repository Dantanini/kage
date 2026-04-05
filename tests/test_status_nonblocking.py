"""Tests for /status non-blocking behavior.

/status must respond immediately even when another handler is busy
(e.g. claude -p running for 15 minutes).
"""

import pytest


class TestStatusHandlerRegistration:
    """Verify /status is registered with block=False in the actual app setup."""

    def test_status_handler_is_non_blocking(self):
        """The CommandHandler for /status in main() must have block=False."""
        from telegram.ext import CommandHandler
        import bot

        # Inspect the actual handler registration code by building the app
        # the same way main() does
        app = bot.Application.builder().token("fake:token").build()

        # Register handlers exactly as main() does
        bot._register_handlers(app)

        # Find the status handler
        status_handlers = [
            h for group_handlers in app.handlers.values()
            for h in group_handlers
            if isinstance(h, CommandHandler) and "status" in h.commands
        ]
        assert len(status_handlers) == 1, f"Expected 1 status handler, found {len(status_handlers)}"
        assert status_handlers[0].block is False, \
            "status handler must be non-blocking (block=False) to respond during long tasks"
