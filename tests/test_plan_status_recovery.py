"""Tests for EXECUTING → PLANNED downgrade on restart.

When bot restarts and plan status is EXECUTING but no claude subprocess
is running, status should be downgraded to PLANNED so buttons match.
"""

from unittest.mock import AsyncMock, patch, MagicMock, PropertyMock
import pytest
from plan_v2 import PlanStatus


def _mock_plan_store(status: PlanStatus):
    store = MagicMock()
    store.status = status
    store.pending_items.return_value = ["- [ ] task A"]
    store.read_planned.return_value = "- [ ] task A"
    store.read_completed.return_value = ""
    store.read_draft.return_value = ""
    store.draft_items.return_value = []
    store.parse_planned_items.return_value = [{"task": "task A", "branch": None, "repo": None}]
    store.has_plan.return_value = True
    return store


class TestDowngradeExecutingOnRestart:
    """post_init should downgrade EXECUTING → PLANNED when no subprocess."""

    @pytest.mark.asyncio
    async def test_executing_without_process_becomes_planned(self):
        """EXECUTING + no claude process → downgrade to PLANNED."""
        store = _mock_plan_store(PlanStatus.EXECUTING)

        with patch("bot.plan_store", store), \
             patch("bot._get_claude_status", new_callable=AsyncMock, return_value=None), \
             patch("bot.ADMIN_ID", 123), \
             patch("bot.REPO_DIR", MagicMock()):
            import bot
            app = MagicMock()
            app.bot = AsyncMock()
            app.bot.set_my_commands = AsyncMock()

            with patch("pathlib.Path.exists", return_value=False):
                await bot.post_init(app)

            store.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_executing_with_process_stays_executing(self):
        """EXECUTING + claude process running → do NOT downgrade."""
        store = _mock_plan_store(PlanStatus.EXECUTING)
        status_info = {"pid": 12345, "model": "opus", "elapsed": "02:00", "state": "Sl"}

        with patch("bot.plan_store", store), \
             patch("bot._get_claude_status", new_callable=AsyncMock, return_value=status_info), \
             patch("bot.ADMIN_ID", 123), \
             patch("bot.REPO_DIR", MagicMock()):
            import bot
            app = MagicMock()
            app.bot = AsyncMock()
            app.bot.set_my_commands = AsyncMock()

            with patch("pathlib.Path.exists", return_value=False):
                await bot.post_init(app)

            store.pause.assert_not_called()

    @pytest.mark.asyncio
    async def test_planned_not_affected(self):
        """PLANNED status should not trigger downgrade."""
        store = _mock_plan_store(PlanStatus.PLANNED)

        with patch("bot.plan_store", store), \
             patch("bot._get_claude_status", new_callable=AsyncMock, return_value=None), \
             patch("bot.ADMIN_ID", 123), \
             patch("bot.REPO_DIR", MagicMock()):
            import bot
            app = MagicMock()
            app.bot = AsyncMock()
            app.bot.set_my_commands = AsyncMock()

            with patch("pathlib.Path.exists", return_value=False):
                await bot.post_init(app)

            store.pause.assert_not_called()

    @pytest.mark.asyncio
    async def test_recovery_message_after_downgrade_is_planned(self):
        """After downgrade, recovery buttons should be PLANNED style (has execute button)."""
        store = _mock_plan_store(PlanStatus.EXECUTING)

        # After pause() is called, status should read as PLANNED
        def fake_pause():
            store.status = PlanStatus.PLANNED
        store.pause.side_effect = fake_pause

        with patch("bot.plan_store", store), \
             patch("bot._get_claude_status", new_callable=AsyncMock, return_value=None), \
             patch("bot.ADMIN_ID", 123), \
             patch("bot.REPO_DIR", MagicMock()):
            import bot
            app = MagicMock()
            app.bot = AsyncMock()
            app.bot.set_my_commands = AsyncMock()

            with patch("pathlib.Path.exists", return_value=False):
                await bot.post_init(app)

            # Check recovery message was sent with execute button
            assert app.bot.send_message.called
            call_kwargs = app.bot.send_message.call_args
            if hasattr(call_kwargs, 'kwargs') and 'reply_markup' in call_kwargs.kwargs:
                keyboard = call_kwargs.kwargs['reply_markup']
            else:
                keyboard = call_kwargs[1].get('reply_markup') if len(call_kwargs) > 1 else None

            if keyboard:
                button_data = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
                assert "plan_execute" in button_data
